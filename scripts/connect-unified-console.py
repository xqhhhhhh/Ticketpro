"""Install a small opt-in filter without touching its project credentials or databases."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('console_directory', type=Path)
args = parser.parse_args()
source = args.console_directory / 'app.py'
text = source.read_text()
hook = 'from unified_reservations import website_reservations, is_website_code'
if hook not in text:
    old = '''    normalized_binding_mode = "none" if str(binding_mode or "").strip().lower() in {"none", "unbound"} else "machine"
    size = max(20, min(100, len(exclude) + 5))'''
    new = '''    normalized_binding_mode = "none" if str(binding_mode or "").strip().lower() in {"none", "unbound"} else "machine"
    try:
        reserved = website_reservations(project.id)
    except (OSError, ValueError, TypeError):
        raise HTTPException(status_code=503, detail="网站库存隔离清单不可读，已暂停人工取码") from None
    size = max(20, min(100 if project.api_type == "available" else 500, len(exclude) + len(reserved) + 5))'''
    pick = '    code = next((candidate for candidate in codes if candidate.upper() not in excluded), "")'
    replacement = '''    code = next((candidate for candidate in codes
                 if candidate.upper() not in excluded and not is_website_code(candidate, reserved)), "")
    total = max(1 if code else 0, total - len(reserved)) if code else 0'''
    if old not in text or pick not in text:
        raise SystemExit('统一管理台源码结构已改变，请人工检查适配点；没有修改任何文件。')
    shutil.copy2(source, source.with_name('app.py.backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')))
    text = text.replace('import base64\n', 'import base64\n' + hook + '\n', 1).replace(old, new, 1).replace(pick, replacement, 1)
    source.write_text(text)
shutil.copy2(Path(__file__).resolve().parents[1] / 'server/unified_reservations.py', args.console_directory / 'unified_reservations.py')
print('已安装网站库存过滤器。设置同一个 UNIFIED_RESERVED_CODES_FILE 后生效，未配置时保持原有取码行为。')
