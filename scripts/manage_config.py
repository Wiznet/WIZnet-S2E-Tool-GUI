#!/usr/bin/env python3
"""
JSON 설정 파일 백업/복원 도구

Usage:
    python manage_config.py backup
    python manage_config.py list
    python manage_config.py restore <index>
    python manage_config.py restore latest
"""

import json
import shutil
import sys
from pathlib import Path
from datetime import datetime
import glob


class ConfigManager:
    """설정 파일 관리자"""

    def __init__(self, config_path: str = 'config/devices/devices_sample.json'):
        self.config_path = Path(config_path)
        self.backup_dir = self.config_path.parent / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self) -> bool:
        """현재 설정 파일을 백업"""
        if not self.config_path.exists():
            print(f"[ERROR] Config file not found: {self.config_path}")
            return False

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"devices_{timestamp}.json"

        try:
            shutil.copy2(self.config_path, backup_path)
            print(f"[OK] Backed up to: {backup_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Backup failed: {e}")
            return False

    def list_backups(self) -> list:
        """백업 목록 조회"""
        backups = sorted(self.backup_dir.glob('devices_*.json'), reverse=True)

        if not backups:
            print("[INFO] No backups found")
            return []

        print(f"\n{'#':<4} {'Filename':<30} {'Size':<10} {'Date':<20}")
        print("=" * 70)

        for i, backup in enumerate(backups, 1):
            size = backup.stat().st_size
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)

            size_str = self._format_size(size)
            date_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

            print(f"{i:<4} {backup.name:<30} {size_str:<10} {date_str:<20}")

        print()
        return backups

    def restore(self, target: str) -> bool:
        """백업에서 복원"""
        backups = sorted(self.backup_dir.glob('devices_*.json'), reverse=True)

        if not backups:
            print("[ERROR] No backups found")
            return False

        # 'latest' 또는 인덱스
        if target.lower() == 'latest':
            backup_path = backups[0]
        else:
            try:
                index = int(target) - 1
                if 0 <= index < len(backups):
                    backup_path = backups[index]
                else:
                    print(f"[ERROR] Invalid index: {target}")
                    return False
            except ValueError:
                print(f"[ERROR] Invalid target: {target}")
                return False

        # 현재 설정 파일을 먼저 백업
        if self.config_path.exists():
            auto_backup = self.backup_dir / f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            shutil.copy2(self.config_path, auto_backup)
            print(f"[INFO] Auto-backed up current config to: {auto_backup.name}")

        # 복원
        try:
            shutil.copy2(backup_path, self.config_path)
            print(f"[OK] Restored from: {backup_path.name}")
            return True
        except Exception as e:
            print(f"[ERROR] Restore failed: {e}")
            return False

    def compare(self, backup1: str, backup2: str = None) -> bool:
        """백업 파일 비교"""
        backups = sorted(self.backup_dir.glob('devices_*.json'), reverse=True)

        if not backups:
            print("[ERROR] No backups found")
            return False

        try:
            idx1 = int(backup1) - 1
            path1 = backups[idx1] if 0 <= idx1 < len(backups) else None

            if backup2:
                idx2 = int(backup2) - 1
                path2 = backups[idx2] if 0 <= idx2 < len(backups) else None
            else:
                path2 = self.config_path

            if not path1 or not path2:
                print("[ERROR] Invalid backup index")
                return False

            # 파일 로드
            with open(path1, 'r', encoding='utf-8') as f:
                config1 = json.load(f)

            with open(path2, 'r', encoding='utf-8') as f:
                config2 = json.load(f)

            # 비교
            print(f"\nComparing:")
            print(f"  File 1: {path1.name}")
            print(f"  File 2: {path2.name}")
            print()

            self._compare_configs(config1, config2)

            return True

        except Exception as e:
            print(f"[ERROR] Compare failed: {e}")
            return False

    def _compare_configs(self, config1: dict, config2: dict):
        """설정 파일 비교 상세"""
        # 명령어 세트 수 비교
        cmdsets1 = config1.get('command_sets', {})
        cmdsets2 = config2.get('command_sets', {})

        print(f"Command Sets: {len(cmdsets1)} vs {len(cmdsets2)}")

        # 장치 모델 수 비교
        models1 = config1.get('device_models', {})
        models2 = config2.get('device_models', {})

        print(f"Device Models: {len(models1)} vs {len(models2)}")

        # 추가/삭제된 모델
        models1_set = set(models1.keys())
        models2_set = set(models2.keys())

        added = models2_set - models1_set
        removed = models1_set - models2_set

        if added:
            print(f"\nAdded models: {', '.join(added)}")
        if removed:
            print(f"\nRemoved models: {', '.join(removed)}")

    def _format_size(self, size: int) -> str:
        """파일 크기 포맷팅"""
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size/1024:.1f}KB"
        else:
            return f"{size/(1024*1024):.1f}MB"

    def clean_old_backups(self, keep: int = 10) -> bool:
        """오래된 백업 정리"""
        backups = sorted(self.backup_dir.glob('devices_*.json'), reverse=True)

        if len(backups) <= keep:
            print(f"[INFO] {len(backups)} backups (keeping all)")
            return True

        # auto_backup 제외
        auto_backups = sorted(self.backup_dir.glob('auto_backup_*.json'), reverse=True)
        regular_backups = [b for b in backups if b not in auto_backups]

        to_delete = regular_backups[keep:]

        if not to_delete:
            print(f"[INFO] No old backups to delete")
            return True

        print(f"[INFO] Deleting {len(to_delete)} old backup(s)...")

        for backup in to_delete:
            try:
                backup.unlink()
                print(f"  Deleted: {backup.name}")
            except Exception as e:
                print(f"  [ERROR] Failed to delete {backup.name}: {e}")

        return True


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Manage JSON configuration backups"
    )
    parser.add_argument(
        'command',
        choices=['backup', 'list', 'restore', 'compare', 'clean'],
        help='Command to execute'
    )
    parser.add_argument(
        'args',
        nargs='*',
        help='Command arguments'
    )
    parser.add_argument(
        '--config',
        default='config/devices/devices_sample.json',
        help='Config file path'
    )

    args = parser.parse_args()

    manager = ConfigManager(args.config)

    if args.command == 'backup':
        success = manager.backup()
        sys.exit(0 if success else 1)

    elif args.command == 'list':
        manager.list_backups()
        sys.exit(0)

    elif args.command == 'restore':
        if not args.args:
            print("[ERROR] Usage: manage_config.py restore <index|latest>")
            sys.exit(1)
        success = manager.restore(args.args[0])
        sys.exit(0 if success else 1)

    elif args.command == 'compare':
        if not args.args:
            print("[ERROR] Usage: manage_config.py compare <index> [index2]")
            sys.exit(1)
        backup2 = args.args[1] if len(args.args) > 1 else None
        success = manager.compare(args.args[0], backup2)
        sys.exit(0 if success else 1)

    elif args.command == 'clean':
        keep = int(args.args[0]) if args.args else 10
        success = manager.clean_old_backups(keep)
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
