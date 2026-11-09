import os
import shutil
import tarfile
import tempfile
import zipfile
from typing import ClassVar, Literal

_TarMode = Literal["r", "r:gz", "r:bz2", "r:xz"]


class NestedArchiveExtractor:
    """嵌套压缩包解压器"""

    SUPPORTED: ClassVar[frozenset[str]] = frozenset(
        {".zip", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".xz", ".txz", ".lzma"}
    )
    TAR_MODES: ClassVar[dict[str, _TarMode]] = {
        ".tar": "r",
        ".gz": "r:gz",
        ".tgz": "r:gz",
        ".bz2": "r:bz2",
        ".tbz2": "r:bz2",
        ".xz": "r:xz",
        ".txz": "r:xz",
        ".lzma": "r:xz",
    }

    def __init__(self, output_dir: str):
        self.output_dir = os.path.abspath(output_dir)
        os.makedirs(self.output_dir, exist_ok=True)
        self.processed = set()

    def is_archive(self, path: str) -> bool:
        """检查是否为支持的压缩格式"""
        ext = os.path.splitext(path)[1].lower()
        if ext in self.SUPPORTED:
            return True

        # 检查双扩展名 (.tar.gz, .tar.bz2 等)
        _, ext2 = os.path.splitext(os.path.splitext(path)[0])
        return f"{ext2}{ext}" in {".tar.gz", ".tar.bz2", ".tar.xz", ".tar.lzma"}

    def _is_safe_path(self, path: str, target_dir: str) -> bool:
        """检查文件路径是否在目标目录内，防止路径遍历攻击"""
        try:
            return os.path.commonpath(
                [os.path.abspath(path), os.path.abspath(target_dir)]
            ) == os.path.abspath(target_dir)
        except ValueError:
            return False

    def _collect_files(self, target_dir: str) -> list[str]:
        """收集目录下所有文件路径"""
        return [
            os.path.join(root, filename)
            for root, _, filenames in os.walk(target_dir)
            for filename in filenames
        ]

    def _extract_archive(self, archive: str, target_dir: str) -> None:
        """安全解压压缩包"""
        ext = os.path.splitext(archive)[1].lower()

        if ext == ".zip":
            with zipfile.ZipFile(archive, "r") as z:
                for member in z.namelist():
                    target_path = os.path.join(target_dir, member)
                    if self._is_safe_path(target_path, target_dir):
                        z.extract(member, target_dir)
                    else:
                        print(f"警告: 跳过潜在不安全的路径: {member}")
            return

        # 处理双扩展名
        _, ext2 = os.path.splitext(os.path.splitext(archive)[0])
        if ext2:
            double = f"{ext2}{ext}"
            if double in {".tar.gz", ".tar.bz2", ".tar.xz"}:
                ext = "." + double.split(".")[-1]

        if ext in self.TAR_MODES:
            with tarfile.open(archive, self.TAR_MODES[ext]) as t:
                for member in t.getmembers():
                    target_path = os.path.join(target_dir, member.name)
                    if self._is_safe_path(target_path, target_dir):
                        t.extract(member, target_dir)
                    else:
                        print(f"警告: 跳过潜在不安全的路径: {member.name}")
            return

        raise ValueError(f"不支持的格式: {ext}")

    def _rename_move(self, src: str, prefix: str) -> str:
        """重命名并移动文件"""
        src_name = os.path.basename(src)
        src_stem, src_ext = os.path.splitext(src_name)
        dst = os.path.join(self.output_dir, f"{prefix}_{src_name}")

        # 处理重名
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(
                self.output_dir, f"{prefix}_{src_stem}_{counter}{src_ext}"
            )
            counter += 1

        shutil.move(src, dst)
        return dst

    def extract(self, archive: str, prefix: str | None = None) -> list[str]:
        """递归解压压缩包"""
        archive = os.path.abspath(archive)
        if not os.path.exists(archive):
            raise FileNotFoundError(archive)

        # 防循环处理
        real_path = os.path.abspath(archive)
        if real_path in self.processed:
            return []
        self.processed.add(real_path)

        prefix = prefix or os.path.splitext(os.path.basename(archive))[0]
        print(f"解压: {os.path.basename(archive)} -> 前缀: {prefix}")

        with tempfile.TemporaryDirectory() as tmp:
            self._extract_archive(archive, tmp)
            files = self._collect_files(tmp)

            result = []
            for file_path in files:
                if os.path.isfile(file_path):
                    if self.is_archive(file_path):
                        # 递归解压子压缩包
                        sub_prefix = f"{prefix}_{os.path.splitext(os.path.basename(file_path))[0]}"
                        result.extend(self.extract(file_path, sub_prefix))
                    else:
                        # 普通文件：重命名并移动
                        result.append(self._rename_move(file_path, prefix))
            return result


# 使用示例
if __name__ == "__main__":
    extractor = NestedArchiveExtractor("./output")
    files = extractor.extract("./nested.zip")
    print(f"共解压 {len(files)} 个文件")
