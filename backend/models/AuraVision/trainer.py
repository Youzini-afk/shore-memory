import os

import torch
import torch.nn as nn
import torch.optim as optim
from loguru import logger
from torch.utils.data import DataLoader

from .dataset import AuraVisionDataset
from .model import AuraVisionEncoder

try:
    from safetensors.torch import save_file

    HAS_SAFETENSORS = True
except ImportError:
    HAS_SAFETENSORS = False


class IntentLoss(nn.Module):
    """
    用于语义对齐的三元组损失 (Triplet Loss)
    """

    def __init__(self, margin=0.5):
        super().__init__()
        self.margin = margin

    def forward(self, anchor, positive, negative):
        # 欧几里得距离
        pos_dist = (anchor - positive).pow(2).sum(1)
        neg_dist = (anchor - negative).pow(2).sum(1)
        # 三元组损失公式: relu(d(a,p) - d(a,n) + margin)
        loss = torch.clamp(pos_dist - neg_dist + self.margin, min=0.0)
        return loss.mean()


class AuraVisionTrainer:
    def __init__(self, model=None, lr=1e-4, device=None):
        self.device = device or torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )
        self.model = model or AuraVisionEncoder()
        self.model.to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-2)
        self.criterion = IntentLoss(margin=0.5)
        logger.info(f"AuraVisionTrainer 已在 {self.device} 上初始化")

    def train_epoch(self, dataloader):
        self.model.train()
        total_loss = 0
        for _batch_idx, (anchor, pos, neg) in enumerate(dataloader):
            anchor, pos, neg = (
                anchor.to(self.device),
                pos.to(self.device),
                neg.to(self.device),
            )

            self.optimizer.zero_grad()

            # 前向传播
            v_a = self.model(anchor)
            v_p = self.model(pos)
            v_n = self.model(neg)

            # 计算损失
            loss = self.criterion(v_a, v_p, v_n)

            # 反向传播
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item()

        return total_loss / len(dataloader)

    def save_checkpoint(self, path, use_safetensors=True):
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if use_safetensors and HAS_SAFETENSORS:
            # Safetensors 是 Candle 框架的首选格式
            state_dict = self.model.state_dict()
            # 确保所有张量是连续的
            state_dict = {k: v.contiguous() for k, v in state_dict.items()}
            save_file(state_dict, path)
            logger.info(f"模型已保存至 {path} (Safetensors)")
        else:
            torch.save(self.model.state_dict(), path)
            logger.info(f"模型已保存至 {path} (PyTorch .pth)")


def train_aura_vision(vision_data_dir, epochs=50, batch_size=16, save_path=None):
    if save_path is None:
        # 默认保存路径相对于脚本目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        save_path = os.path.join(base_dir, "weights", "auravision_v1.safetensors")

    dataset = AuraVisionDataset(vision_data_dir, mode="edge")
    if len(dataset) < 2:
        logger.error("样本数量太少，无法训练。")
        return None

    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    trainer = AuraVisionTrainer(lr=2e-4)  # 稍微调高学习率

    logger.info(f"开始训练 AuraVision... 样本数: {len(dataset)}, 轮次: {epochs}")

    for epoch in range(epochs):
        avg_loss = trainer.train_epoch(dataloader)
        if (epoch + 1) % 5 == 0:
            logger.info(f"Epoch {epoch + 1}/{epochs} - Loss: {avg_loss:.4f}")

    trainer.save_checkpoint(save_path)
    return trainer.model


if __name__ == "__main__":
    # 自动定位 vision_data 目录
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    # 假设 vision_data 在 backend/scripts/vision_data
    VISION_DATA_DIR = os.path.abspath(
        os.path.join(SCRIPT_DIR, "../../scripts/vision_data")
    )

    if os.path.exists(VISION_DATA_DIR):
        train_aura_vision(VISION_DATA_DIR, epochs=100, batch_size=16)
    else:
        logger.error(f"找不到数据目录: {VISION_DATA_DIR}")
