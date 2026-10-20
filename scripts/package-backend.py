"""Build a server-only release, excluding passwords, stock, databases and frontend assets."""
import argparse
import os
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=ROOT / 'output/ticketpro-backend.tar.gz')
args = parser.parse_args()
files = sorted((ROOT / 'server').glob('*.py'))
files += [ROOT / 'server' / name for name in ['requirements.lock', 'catalog.json', 'product-projects.json',
                                             'license-projects.json', 'tutorials.local.json']]
files += sorted((ROOT / 'deploy').glob('*'))
files += [ROOT / 'scripts/connect-unified-console.py', ROOT / 'scripts/configure-stock-sources.py', ROOT / 'docs/payment-delivery.md']
if any(not path.is_file() for path in files):
    raise SystemExit('服务端源码或教程配置缺失，未生成部署包。')
args.output.parent.mkdir(parents=True, exist_ok=True)
fd = os.open(args.output, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
with os.fdopen(fd, 'wb') as stream:
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for path in files:
            archive.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
args.output.chmod(0o600)
print(f'已生成服务端部署包：{args.output.resolve()}（{len(files)} 个文件，不含支付密钥、库存或订单数据库）')
