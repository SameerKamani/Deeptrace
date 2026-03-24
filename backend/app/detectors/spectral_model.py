from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path
from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class LayerNorm(nn.Module):
    def __init__(self, normalized_shape: int, eps: float = 1e-6, data_format: str = "channels_last"):
        super().__init__()
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.bias = nn.Parameter(torch.zeros(normalized_shape))
        self.eps = eps
        self.data_format = data_format
        self.normalized_shape = (normalized_shape,)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.data_format == "channels_last":
            return F.layer_norm(x, self.normalized_shape, self.weight, self.bias, self.eps)
        # channels_first
        mean = x.mean(1, keepdim=True)
        var = (x - mean).pow(2).mean(1, keepdim=True)
        x = (x - mean) / torch.sqrt(var + self.eps)
        return self.weight[:, None, None] * x + self.bias[:, None, None]


class MLP(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.fc1 = nn.Linear(dim, 4 * dim)
        self.act = nn.GELU()
        self.fc2 = nn.Linear(4 * dim, dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.fc2(self.act(self.fc1(x)))


class ConvNeXtBlock(nn.Module):
    def __init__(self, dim: int, layer_scale_init_value: float = 1e-6):
        super().__init__()
        self.conv_dw = nn.Conv2d(dim, dim, kernel_size=7, padding=3, groups=dim)
        self.norm = LayerNorm(dim, eps=1e-6, data_format="channels_last")
        self.mlp = MLP(dim)
        self.gamma = nn.Parameter(layer_scale_init_value * torch.ones(dim))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shortcut = x
        x = self.conv_dw(x)
        x = x.permute(0, 2, 3, 1)
        x = self.norm(x)
        x = self.mlp(x)
        x = x * self.gamma
        x = x.permute(0, 3, 1, 2)
        return shortcut + x


class ConvNeXtStage(nn.Module):
    def __init__(self, in_dim: int, out_dim: int, depth: int, downsample: bool):
        super().__init__()
        if downsample:
            self.downsample = nn.Sequential(
                LayerNorm(in_dim, eps=1e-6, data_format="channels_first"),
                nn.Conv2d(in_dim, out_dim, kernel_size=2, stride=2),
            )
        else:
            self.downsample = None
        self.blocks = nn.ModuleList([ConvNeXtBlock(out_dim) for _ in range(depth)])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.downsample is not None:
            x = self.downsample(x)
        for block in self.blocks:
            x = block(x)
        return x


class SemanticBranch(nn.Module):
    def __init__(self, dims: Tuple[int, int, int, int], depths: Tuple[int, int, int, int]):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv2d(3, dims[0], kernel_size=4, stride=4),
            LayerNorm(dims[0], eps=1e-6, data_format="channels_first"),
        )
        self.stages = nn.ModuleList(
            [
                ConvNeXtStage(dims[0], dims[0], depths[0], downsample=False),
                ConvNeXtStage(dims[0], dims[1], depths[1], downsample=True),
                ConvNeXtStage(dims[1], dims[2], depths[2], downsample=True),
                ConvNeXtStage(dims[2], dims[3], depths[3], downsample=True),
            ]
        )
        self.head = nn.ModuleDict({"norm": nn.LayerNorm(dims[3])})

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)
        for stage in self.stages:
            x = stage(x)
        x = x.mean(dim=[2, 3])
        x = self.head["norm"](x)
        return x


class SpectralFusionModel(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        # Standard RGB to Grayscale Luma Weights (BT.601)
        self.gray_weights = nn.Parameter(torch.tensor([[[[0.299]], [[0.587]], [[0.114]]]]), requires_grad=False)
        
        # 1. Semantic Branch (ConvNeXt)
        self.semantic_branch = SemanticBranch(
            dims=(96, 192, 384, 768),
            depths=(3, 3, 27, 3),
        )
        
        # 2. Spectral Branch (FFT)
        self.spectral_branch = nn.Sequential(
            nn.Flatten(1),
            nn.Identity(),
            nn.Linear(4096, 256)
        )
        
        # 3. SRM Branch
        self.srm_conv = nn.Conv2d(1, 3, kernel_size=5, padding=2, bias=False)
        self.srm_branch = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((16, 16)),
            nn.Flatten(1),
            nn.Linear(8192, 256)
        )
        
        # 4. Chroma Branch
        self.chroma_branch = nn.Sequential(
            nn.Conv2d(2, 16, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((32, 32)),
            nn.Flatten(1),
            nn.Linear(16384, 128)
        )
        
        # 5. SPAI Branch
        self.spai_branch = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d((32, 32)),
            nn.Flatten(1),
            nn.Linear(32768, 256)
        )
        
        # 6. Robustness Branch
        self.robustness_branch = nn.Sequential(
            nn.Linear(768, 256),
            nn.ReLU(),
            nn.Linear(256, 128)
        )

        # Final Fusion Head
        self.fusion_head = nn.Sequential(
            nn.Linear(1792, 1024),
            nn.ReLU(inplace=True),
            nn.Dropout(p=0.2),
            nn.Linear(1024, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # 1. Semantic
        semantic_features = self.semantic_branch(x)

        # Compute Gray for FFT, SRM, and SPAI
        gray = (x * self.gray_weights).sum(dim=1, keepdim=True)
        
        # 2. Spectral (FFT)
        fft = torch.fft.fft2(gray)
        magnitude = torch.abs(fft)
        magnitude = torch.log1p(magnitude)
        magnitude = F.interpolate(magnitude, size=(64, 64), mode="bilinear", align_corners=False)
        spectral_features = self.spectral_branch(magnitude)
        
        # 3. SRM
        srm_residuals = self.srm_conv(gray) 
        srm_features = self.srm_branch(srm_residuals)
        
        # 4. Chroma (YcbCr approximation)
        r, g, b = x[:, 0:1], x[:, 1:2], x[:, 2:3]
        cb = -0.1687 * r - 0.3313 * g + 0.5 * b
        cr = 0.5 * r - 0.4187 * g - 0.0813 * b
        chroma = torch.cat([cb, cr], dim=1)
        chroma_features = self.chroma_branch(chroma)
        
        # 5. SPAI
        spai_features = self.spai_branch(gray)
        
        # 6. Robustness
        robustness_features = self.robustness_branch(semantic_features)

        # Fuse
        fused = torch.cat([
            semantic_features,    # 768
            spectral_features,    # 256
            srm_features,         # 256
            chroma_features,      # 128
            spai_features,        # 256
            robustness_features   # 128
        ], dim=1)                 # Total: 1792
        
        return self.fusion_head(fused)


def load_state_dict_from_path(path: str) -> dict:
    model_path = Path(path)
    if model_path.is_dir():
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pt")
        tmp.close()
        with zipfile.ZipFile(tmp.name, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for file_path in model_path.rglob("*"):
                if file_path.is_file():
                    arcname = str(Path(model_path.name) / file_path.relative_to(model_path))
                    zf.write(file_path, arcname)
        load_path = tmp.name
    else:
        load_path = str(model_path)
    return torch.load(load_path, map_location="cpu")
