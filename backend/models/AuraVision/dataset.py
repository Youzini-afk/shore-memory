import json
import os
import random

from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms


class AuraVisionDataset(Dataset):
    """
    Pero AuraVision 三元组训练数据集
    自动从 vision_data 目录加载 (Raw, Edge, Gray) 和意图标签。
    """

    def __init__(self, vision_data_dir, transform=None, mode="edge"):
        """
        Args:
            vision_data_dir: 'vision_data' 目录的路径。
            transform: 自定义转换。
            mode: "edge", "gray" 或 "raw"。
        """
        self.input_dir = os.path.join(vision_data_dir, "input")
        self.output_dir = os.path.join(vision_data_dir, "output")
        self.mode = mode

        # 1. 扫描有效的组（必须同时具有图像和 json）
        self.samples = []
        json_files = [f for f in os.listdir(self.output_dir) if f.endswith(".json")]

        # 按时间戳分组
        self.label_to_indices = {}

        for jf in json_files:
            # 匹配 pero_view_{ts}_label.json
            if not jf.startswith("pero_view_") or not jf.endswith("_label.json"):
                continue

            ts = jf.replace("pero_view_", "").replace("_label.json", "")
            img_name = f"pero_view_{ts}_{mode}.png"
            img_path = os.path.join(self.input_dir, img_name)
            json_path = os.path.join(self.output_dir, jf)

            if os.path.exists(img_path):
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        label = data.get("intent", "未知")
                        # 简化标签，只取大类以提高收敛速度
                        main_label = label.split(":")[0].strip()

                        idx = len(self.samples)
                        self.samples.append(
                            {"ts": ts, "img_path": img_path, "label": main_label}
                        )

                        if main_label not in self.label_to_indices:
                            self.label_to_indices[main_label] = []
                        self.label_to_indices[main_label].append(idx)
                except Exception as e:
                    print(f"警告: 无法加载 {jf}: {e}")

        self.labels = list(self.label_to_indices.keys())
        print(f"加载了 {len(self.samples)} 个样本，共 {len(self.labels)} 个意图类别")

        # 针对脱敏后的 64x64 图像的默认转换
        self.transform = transform or transforms.Compose(
            [
                transforms.Resize((64, 64)),
                transforms.ToTensor(),
                transforms.RandomErasing(p=0.3, scale=(0.02, 0.1)),
                transforms.Normalize((0.5,), (0.5,)),
            ]
        )

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        # 1. 锚点 (Anchor)
        anchor_sample = self.samples[index]
        anchor_label = anchor_sample["label"]
        anchor_img = self._load_img(anchor_sample["img_path"])

        # 2. 正样本 (Positive)
        pos_indices = self.label_to_indices[anchor_label]
        if len(pos_indices) > 1:
            pos_idx = random.choice([i for i in pos_indices if i != index])
        else:
            pos_idx = index
        pos_img = self._load_img(self.samples[pos_idx]["img_path"])

        # 3. 负样本 (Negative)
        other_labels = [label for label in self.labels if label != anchor_label]
        if not other_labels:
            neg_idx = index
        else:
            neg_label = random.choice(other_labels)
            neg_idx = random.choice(self.label_to_indices[neg_label])
        neg_img = self._load_img(self.samples[neg_idx]["img_path"])

        return anchor_img, pos_img, neg_img

    def _load_img(self, path):
        img = Image.open(path).convert("L")
        if self.transform:
            img = self.transform(img)
        return img


def get_default_transform():
    return transforms.Compose(
        [
            transforms.RandomRotation(5),
            transforms.ColorJitter(brightness=0.2, contrast=0.2),
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,)),
        ]
    )
