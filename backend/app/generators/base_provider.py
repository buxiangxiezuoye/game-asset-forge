"""
可插拔 AI 图像生成器抽象基类。

所有 Provider 必须实现 generate() 方法。
默认模式是 mock（程序化生成），AI Provider 仅在使用者配置了
IMAGE_PROVIDER_MODE=http 时启用。
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from PIL import Image


class BaseImageProvider(ABC):
    """AI 图像生成 Provider 抽象基类。"""

    @abstractmethod
    def generate(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        width: int = 64,
        height: int = 64,
        seed: int = 0,
    ) -> Image.Image:
        """
        生成单张 RGBA/PNG 图像。

        调用方负责：
          - 拼接 stylePromptPrefix + userPrompt
          - 提供 negative_prompt（从 StyleService 获取）

        Returns:
            PIL Image (RGBA)

        Raises:
            RuntimeError: 生成失败时抛出
        """
        ...
