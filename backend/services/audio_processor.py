import logging
import os

import parselmouth
from parselmouth.praat import call

logger = logging.getLogger(__name__)


class AudioProcessor:
    """
    音频后处理服务，调整音高/共振峰使声音更可爱。
    """

    @staticmethod
    async def process_voice_cute(
        input_path: str,
        output_path: str,
        pitch_factor: float = 1.2,
        formant_factor: float = 1.1,
    ) -> bool:
        """调整音高和共振峰使声音变可爱。"""
        try:
            if not os.path.exists(input_path):
                logger.error(f"未找到输入文件: {input_path}")
                return False

            # 加载声音
            sound = parselmouth.Sound(input_path)

            # 使用 Praat "Change gender" 调整音高/共振峰。
            # 参数：75-600 共振峰范围，后为共振峰/音高偏移、范围比(1.0)、时长比(1.0)。

            new_sound = call(
                sound,
                "Change gender",
                75.0,
                600.0,
                formant_factor,
                pitch_factor,
                1.0,
                1.0,
            )

            # 保存结果
            # 输出 mp3 需先存 wav (parselmouth 不支持)
            if output_path.lower().endswith(".mp3"):
                temp_wav = output_path.replace(".mp3", "_temp.wav")
                new_sound.save(temp_wav, "WAV")

                # 使用 ffmpeg 转换 (若装 pydub)
                try:
                    from pydub import AudioSegment

                    audio = AudioSegment.from_wav(temp_wav)
                    audio.export(output_path, format="mp3")
                    if os.path.exists(temp_wav):
                        os.remove(temp_wav)
                except ImportError:
                    logger.warning("未安装 pydub，保留 wav 格式作为后备")
                    # 无 pydub 则存为 wav
                    new_sound.save(output_path, "WAV")
            else:
                new_sound.save(output_path, "WAV")

            return True

        except Exception as e:
            logger.error(f"处理音频出错: {e}")
            return False


# 单例实例
audio_processor = AudioProcessor()
