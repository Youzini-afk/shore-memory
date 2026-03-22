import torch
import torch.nn as nn
import torch.nn.functional as F


class DepthwiseSeparableConv(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size, stride=1, padding=1):
        super().__init__()
        self.depthwise = nn.Conv2d(
            in_channels,
            in_channels,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            groups=in_channels,
        )
        self.pointwise = nn.Conv2d(in_channels, out_channels, kernel_size=1)
        self.bn = nn.BatchNorm2d(out_channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        x = self.depthwise(x)
        x = self.pointwise(x)
        x = self.bn(x)
        x = self.relu(x)
        return x


class AuraVisionEncoder(nn.Module):
    """
    Pero AuraVision Hybrid Intent Encoder
    Input: (B, 1, 64, 64) - Desensitized grayscale/edge image
    Output: (B, 384) - L2 Normalized Intent Vector
    """

    def __init__(self, embed_dim=128, num_layers=3, num_heads=4, mlp_ratio=2.0):
        super().__init__()

        # 1. 空间组合主干 (CNN)
        # 64x64 -> 32x32
        self.stem_l1 = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(16),
            nn.ReLU(inplace=True),
        )
        # 32x32 -> 16x16
        self.stem_l2 = DepthwiseSeparableConv(
            16, embed_dim, kernel_size=3, stride=2, padding=1
        )

        # 2. 语义 Transformer 块
        self.pos_embed = nn.Parameter(torch.zeros(1, 16 * 16, embed_dim))

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embed_dim,
            nhead=num_heads,
            dim_feedforward=int(embed_dim * mlp_ratio),
            activation="gelu",
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # 3. 意图投影颈部
        self.neck = nn.Sequential(
            nn.Linear(embed_dim, 384), nn.LayerNorm(384), nn.GELU(), nn.Linear(384, 384)
        )

    def forward(self, x):
        # x: (B, 1, 64, 64)

        # 主干输出: (B, 128, 16, 16)
        x = self.stem_l1(x)
        x = self.stem_l2(x)

        # 展平为 tokens: (B, 256, 128)
        B, C, H, W = x.shape
        x = x.view(B, C, H * W).transpose(1, 2)

        # 添加位置编码
        x = x + self.pos_embed

        # Transformer 输出: (B, 256, 128)
        x = self.transformer(x)

        # 全局平均池化 (GAP)
        # 不使用 [CLS] token，而是对所有 token 取平均以捕获「氛围」
        x = x.mean(dim=1)  # (B, 128)

        # 投影输出: (B, 384)
        x = self.neck(x)

        # L2 归一化（用于余弦相似度）
        x = F.normalize(x, p=2, dim=1)

        return x


if __name__ == "__main__":
    # 测试形状
    model = AuraVisionEncoder()
    test_input = torch.randn(1, 1, 64, 64)
    output = model(test_input)
    print(f"Input shape: {test_input.shape}")
    print(f"Output shape: {output.shape}")  # Should be (1, 384)
    print(f"L2 Norm: {torch.norm(output, p=2, dim=1).item()}")  # Should be ~1.0
