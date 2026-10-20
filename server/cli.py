import argparse
import json
import os
from pathlib import Path

import httpx

from .config import ROOT, Settings
from .licenses import prepare_stock
from .store import ShopError, Store
from .tutorials import load_tutorials


def main():
    parser = argparse.ArgumentParser(description='TicketPro 订单与专用库存管理（不打印激活码）')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('summary')
    reconcile = commands.add_parser('reconcile')
    reconcile.add_argument('--limit', type=int, default=200)
    commands.add_parser('demo-seed')
    check = commands.add_parser('check', help='只读检查正式配置、库存与隔离清单')
    check.add_argument('--product', action='append', help='只检查指定商品，可重复使用')
    check.add_argument('--config-only', action='store_true')
    check.add_argument('--online', action='store_true')
    backup = commands.add_parser('backup', help='备份订单数据库与完整交付配置')
    backup.add_argument('--directory', default=os.getenv('TICKETPRO_BACKUP_DIR', 'server/backups'))
    imp = commands.add_parser('import-stock')
    for name in ['product', 'project', 'days', 'batch', 'file']:
        imp.add_argument('--' + name, required=True, type=int if name == 'days' else str)
    imp.add_argument('--tutorial', default='')
    imp.add_argument('--registry', default=os.getenv('UNIFIED_LICENSE_CONFIG', str(ROOT / 'license-projects.json')))
    imp.add_argument('--manifest', default=os.getenv('UNIFIED_RESERVED_CODES_FILE', ''))
    args = parser.parse_args()
    settings = Settings.from_env()
    if args.command == 'check':
        from .readiness import production_check
        report = production_check(settings, args.product, args.config_only, args.online)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report['ready'] else 1
    if args.command == 'backup':
        from .backup import backup_shop
        print(json.dumps(backup_shop(settings, args.directory), ensure_ascii=False, indent=2))
        return 0
    store = Store(settings.db, demo=settings.demo)
    if args.command == 'summary':
        print(json.dumps(store.summary(), ensure_ascii=False, indent=2))
    elif args.command == 'demo-seed':
        if not settings.demo:
            parser.error('仅在 TICKETPRO_DEMO=1 时可生成本地演示库存')
        catalog = json.loads(Path(settings.catalog).read_text())
        items = []
        counts = store.counts()
        for product in catalog:
            for plan in product['plans']:
                if counts.get((product['id'], plan['days']), 0):
                    continue
                for number in range(3):
                    items.append({'product_id': product['id'], 'project_id': product['id'], 'days': plan['days'],
                                  'code': f'DEMO-{product["id"]}-{plan["days"]}-{number}', 'binding_mode': 'machine',
                                  'batch': 'ticketpro-web:local-demo', 'tutorial_url': 'https://example.com/tutorial'})
        if items:
            store.import_stock(items, str(Path(settings.db).with_suffix('.reserved.json')))
        print('本地演示库存已准备，DEMO 码不可用于真实插件。')
    elif args.command == 'import-stock':
        if settings.demo:
            parser.error('演示服务禁止导入正式库存')
        if not args.registry or not args.manifest:
            parser.error('需要 --registry 和 --manifest；统一管理台必须读取同一个隔离清单')
        mapping_path = Path(os.getenv('TICKETPRO_PRODUCT_PROJECTS', str(Path(__file__).with_name('product-projects.json'))))
        mapping = json.loads(mapping_path.read_text())
        if not mapping.get(args.product) or mapping[args.product] != args.project:
            parser.error('商品与授权项目尚未核对或不匹配，请先更新 product-projects.json')
        catalog = json.loads(Path(settings.catalog).read_text())
        if not any(p['id'] == args.product and any(t['days'] == args.days for t in p['plans']) for p in catalog):
            parser.error('商品或期限不在当前商品目录中')
        items = prepare_stock(args.registry, args.product, args.project, args.days, args.batch,
                              Path(args.file).read_text().splitlines(), args.tutorial or load_tutorials(settings.tutorials).get(args.product, ''))
        store.import_stock(items, args.manifest)
        print(f'已验证并导入 {len(items)} 个网站专用码，已更新隔离清单。')
    elif args.command == 'reconcile':
        if settings.demo:
            parser.error('演示订单请使用本地模拟付款页')
        from .gateway import Zpay
        from .reconcile import reconcile_orders
        if not 1 <= args.limit <= 1000:
            parser.error('--limit 必须在 1–1000 之间')
        gateway = Zpay(settings.pid, settings.key, settings.cid, settings.api_url, settings.site_url)
        if not gateway.ready():
            parser.error('正式支付配置尚未就绪')
        result = reconcile_orders(store, gateway, args.limit)
        print(json.dumps(result, ensure_ascii=False))
        return 1 if result['failed'] else 0
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except ShopError as exc:
        raise SystemExit(exc.message) from None
    except (OSError, ValueError):
        raise SystemExit('配置或数据文件缺失、不可读或格式错误；未完成操作。') from None
    except httpx.HTTPError:
        raise SystemExit('原授权接口暂时不可用或凭据无效，未导入库存。') from None
