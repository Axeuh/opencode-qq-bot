# Agent-File 重构任务书

**负责文件:** `src/core/file_handler.py` (932 行)
**目标:** 拆分为 3-4 个小模块
**优先级:** 中

---

## 任务目标

将 `file_handler.py` (932 行) 拆分为职责单一的小模块。

---

## 输出文件结构

```
src/core/file/
    __init__.py              # 导出 FileHandler
    file_handler.py          # FileHandler 核心类 (~200 行)
    downloader.py            # 文件下载逻辑 (~300 行)
    path_resolver.py         # 路径解析和 WSL 转换 (~200 行)
    validator.py             # 文件验证 (~150 行)
```

---

## 详细步骤

### Step 1: 创建目录结构

```bash
mkdir -p src/core/file
touch src/core/file/__init__.py
```

### Step 2: 创建 path_resolver.py

提取路径解析和 WSL 转换逻辑:
```python
import os
import re
from typing import Optional

class PathResolver:
    """路径解析器"""
    
    @staticmethod
    def convert_wsl_to_windows(wsl_path: str) -> str:
        """将 WSL 路径转换为 Windows 路径"""
        # /root/.config/QQ/NapCat/temp/xxx
        # -> \\172.27.213.195\wsl-root\root\.config\QQ\NapCat\temp\xxx
        pass
    
    @staticmethod
    def is_wsl_path(path: str) -> bool:
        """判断是否为 WSL 路径"""
        return path.startswith('/root/') or path.startswith('/home/')
    
    @staticmethod
    def normalize_path(path: str) -> str:
        """规范化路径"""
        pass
    
    @staticmethod
    def get_safe_filename(filename: str) -> str:
        """获取安全的文件名"""
        pass
```

### Step 3: 创建 validator.py

提取文件验证逻辑:
```python
import os
from typing import Optional, Tuple

class FileValidator:
    """文件验证器"""
    
    def __init__(self, config: dict):
        self.config = config
        self.max_size = config.get('max_file_size', 100 * 1024 * 1024)  # 100MB
        self.allowed_extensions = config.get('allowed_extensions', [])
    
    def validate_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """验证文件
        
        Returns:
            (是否有效, 错误信息)
        """
        if not os.path.exists(file_path):
            return False, "文件不存在"
        
        if os.path.getsize(file_path) > self.max_size:
            return False, "文件过大"
        
        ext = os.path.splitext(file_path)[1].lower()
        if self.allowed_extensions and ext not in self.allowed_extensions:
            return False, "不支持的文件类型"
        
        return True, None
    
    @staticmethod
    def is_image(filename: str) -> bool:
        """判断是否为图片"""
        return any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])
```

### Step 4: 创建 downloader.py

提取文件下载逻辑:
```python
import aiohttp
import os
from typing import Optional, Dict, Any
from .path_resolver import PathResolver
from .validator import FileValidator

class FileDownloader:
    """文件下载器"""
    
    def __init__(self, base_dir: str, config: dict, api_callback=None):
        self.base_dir = base_dir
        self.config = config
        self.api_callback = api_callback
        self.path_resolver = PathResolver()
        self.validator = FileValidator(config)
    
    async def download_from_url(self, url: str, filename: str) -> Optional[str]:
        """从 URL 下载文件"""
        pass
    
    async def download_from_forward_msg(self, forward_id: str) -> Dict[str, Any]:
        """下载合并转发消息中的文件"""
        pass
    
    async def _fallback_file_download(self, file_id: str, group_id: int = None) -> Optional[str]:
        """三层回退下载 (重构后的 112 行函数)"""
        # 1. HTTP API 尝试
        result = await self._try_http_api(file_id, group_id)
        if result:
            return result
        
        # 2. WebSocket API 尝试
        result = await self._try_websocket_api(file_id, group_id)
        if result:
            return result
        
        # 3. 字符匹配尝试
        return await self._try_filename_match(file_id)
    
    async def _try_http_api(self, file_id: str, group_id: int = None) -> Optional[str]:
        """尝试通过 HTTP API 下载"""
        pass
    
    async def _try_websocket_api(self, file_id: str, group_id: int = None) -> Optional[str]:
        """尝试通过 WebSocket API 下载"""
        pass
    
    async def _try_filename_match(self, file_id: str) -> Optional[str]:
        """尝试通过文件名匹配"""
        pass
```

### Step 5: 简化 file_handler.py

```python
from typing import Optional, Dict, Any
from .downloader import FileDownloader
from .path_resolver import PathResolver
from .validator import FileValidator

class FileHandler:
    """文件处理器"""
    
    def __init__(self, base_download_dir: str, config: dict, api_callback=None):
        self.downloader = FileDownloader(base_download_dir, config, api_callback)
        self.validator = FileValidator(config)
        self.path_resolver = PathResolver()
    
    async def process_file_message(self, file_info: dict, group_id: int = None, user_id: int = None) -> str:
        """处理文件消息"""
        pass
    
    async def download_file(self, file_id: str, group_id: int = None) -> Optional[str]:
        """下载文件"""
        return await self.downloader._fallback_file_download(file_id, group_id)
    
    # 其他公共方法...
```

---

## 注意事项

### 必须保持不变

1. **FileHandler 公共 API**
   - `process_file_message()` 签名不变
   - `download_file()` 签名不变

2. **三层回退机制**
   - HTTP API -> WebSocket API -> 字符匹配
   - 回退顺序不变

3. **WSL 路径转换**
   - 转换规则不变

### 重构重点

1. **_fallback_file_download() (112 行)**
   - 拆分为 3 个子方法
   - 每个方法 < 50 行

---

## 验证方式

```bash
# 1. 检查语法
python -m py_compile src/core/file/file_handler.py

# 2. 检查导入
python -c "from src.core.file import FileHandler; print('OK')"

# 3. 运行测试
python tests/test_file_handler_api.py
```

---

## 完成标志

- [ ] 目录结构创建完成
- [ ] path_resolver.py 创建完成
- [ ] validator.py 创建完成
- [ ] downloader.py 创建完成
- [ ] file_handler.py 简化完成
- [ ] 测试通过
- [ ] Git 提交

---

## 如有疑问

向 Sisyphus (主协调器) 询问。