"""
字体反爬破解模块：用 fontTools 解析房天下自定义字体，解密价格数字。

工作原理:
  1. 下载 .woff 字体文件 → 计算 MD5
  2. 查 FONT_MAPPING_CACHE: 命中 → 直接用；未命中 → 抛 FontNotCachedError
  3. 人工标定后追加到 constants.py 的 FONT_MAPPING_CACHE
"""

import hashlib

from fontTools.ttLib import TTFont

from crawler.constants import FONT_MAPPING_CACHE


class FontNotCachedError(Exception):
    """新字体文件未标定。

    Attributes:
        font_md5: 字体文件的 MD5 值
        glyphs: {glyph_name: unicode_char} 待标定的加密字形
    """

    def __init__(self, font_md5: str, glyphs: dict[str, str]):
        self.font_md5 = font_md5
        self.glyphs = glyphs
        super().__init__(
            f"字体未标定: MD5={font_md5}, "
            f"共 {len(glyphs)} 个加密 glyph。"
            f"请人工标定后追加到 constants.py 的 FONT_MAPPING_CACHE。"
        )


class FontDecryptor:
    """字体解密器。

    维护当前爬取会话的字符映射表。首次遇到未见过的字体时，
    尝试从 FONT_MAPPING_CACHE 加载；若缓存未命中，抛出 FontNotCachedError
    要求开发者人工标定。

    用法:
        decryptor = FontDecryptor()
        await decryptor.load_font(font_url, fetcher)
        price_text = decryptor.decrypt("驋閏.龒万")
    """

    def __init__(self):
        self._char_map: dict[str, str] = {}  # 加密字符 → 数字字符
        self._loaded_md5: str | None = None

    # ── public API ───────────────────────────────────

    async def load_font(
        self, font_url: str, fetcher: "Fetcher"  # noqa: F821
    ) -> bool:
        """下载字体文件并加载映射表。

        Args:
            font_url: 字体文件 URL（来自 detail_parser）
            fetcher: Fetcher 实例，用于下载字体

        Returns:
            True: 映射表加载成功

        Raises:
            FontNotCachedError: 新字体，需人工标定
        """
        if not font_url:
            return False

        # 下载字体
        font_bytes = await fetcher.download_font_file(font_url)
        font_md5 = hashlib.md5(font_bytes).hexdigest()

        # 已加载过同一字体，跳过
        if self._loaded_md5 == font_md5 and self._char_map:
            return True

        # 1. 查内存缓存
        if font_md5 in FONT_MAPPING_CACHE:
            self._char_map = dict(FONT_MAPPING_CACHE[font_md5])
            self._loaded_md5 = font_md5
            return True

        # 2. 未命中 → 解析字形并抛出异常要求人工标定
        glyphs = self.parse_font_glyphs(font_bytes)
        raise FontNotCachedError(font_md5, glyphs)

    def decrypt(self, raw_text: str) -> str:
        """解密价格文本：逐字符替换加密字符为真实数字。

        不在映射表中的字符原样保留（如小数点、单位等）。

        Args:
            raw_text: 加密的文本，如 "驋閏.龒万"

        Returns:
            解密后的文本，如 "132.5万"
        """
        if not raw_text or not self._char_map:
            return raw_text
        return "".join(self._char_map.get(c, c) for c in raw_text)

    # ── static helpers ───────────────────────────────

    @staticmethod
    def parse_font_glyphs(font_bytes: bytes) -> dict[str, str]:
        """用 fontTools 解析 .woff 字体文件的 CMAP 表。

        提取所有非 ASCII 的 Unicode 字符映射，用于人工标定。

        Args:
            font_bytes: .woff 文件二进制内容

        Returns:
            {glyph_name: unicode_char} — 如 {"uniE001": "", ...}
        """
        font = TTFont(None)  # 先创建空对象
        try:
            # fontTools >= 4.4 支持直接从 bytes 解析
            from io import BytesIO
            font = TTFont(BytesIO(font_bytes))
        except Exception:
            pass

        cmap = font.getBestCmap()
        if not cmap:
            return {}

        glyphs: dict[str, str] = {}
        for unicode_val, glyph_name in cmap.items():
            # 只收集私用区字符（0xE000-0xF8FF）和中日韩字符（>0x2000）
            if "uni" in glyph_name.lower() and (
                0xE000 <= unicode_val <= 0xF8FF or unicode_val > 0x2000
            ):
                glyphs[glyph_name] = chr(unicode_val)

        return glyphs

    @staticmethod
    def suggest_mapping(glyphs: dict[str, str]) -> str:
        """生成标定建议表格，方便开发者对照录入。

        Args:
            glyphs: parse_font_glyphs() 的返回值

        Returns:
            格式化的表格字符串
        """
        lines = ["Glyph Name          | Unicode Char | 对应的数字？"]
        lines.append("-" * 55)
        for glyph_name, char in sorted(glyphs.items()):
            lines.append(f"  {glyph_name:<20} | U+{ord(char):04X}       | ?")
        return "\n".join(lines)
