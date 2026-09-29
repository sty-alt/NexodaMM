# Запуск бота 24/7 на сервере (VPS)

Инструкция для Ubuntu. Для каждого экземпляра бота нужен отдельный токен и каталог данных.

## 1. Возьми VPS
Подготовь сервер с Ubuntu 22.04 или новее и доступом по SSH.

Подключись по SSH:
```bash
ssh root@IP_СЕРВЕРА
```

## 2. Установи Python и инструменты
```bash
apt update && apt install -y python3 python3-pip python3-venv git
```

## 3. Загрузи проект
Скопируй папку проекта в `/opt/nexoda` (через `scp`, `git` или вручную). Затем:
```bash
cd /opt/nexoda
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 4. Настрой `.env`
```bash
cp .env.example .env
nano .env   # впиши BOT_TOKEN и ADMIN_IDS, сохрани (Ctrl+O, Enter, Ctrl+X)
```

(Опционально применить пресет ниши: `python apply_preset.py barbershop`)

## 5. Автозапуск через systemd
Сервис в `deploy/nexoda.service` рассчитан на каталог `/opt/nexoda`. Если путь другой, измени `WorkingDirectory` и `ExecStart`. Затем:
```bash
cp deploy/nexoda.service /etc/systemd/system/nexoda.service
systemctl daemon-reload
systemctl enable nexoda
systemctl start nexoda
```

## 6. Проверка и управление
```bash
systemctl status nexoda      # статус
journalctl -u nexoda -f      # живые логи
systemctl restart nexoda     # перезапуск после изменений
systemctl stop nexoda        # остановить
```

## Несколько клиентов на одном сервере
Для каждого клиента — своя папка и свой сервис:
```bash
cp -r /opt/nexoda /opt/nexoda-barber1
# свой .env (свой BOT_TOKEN), свой unit-файл nexoda-barber1.service с WorkingDirectory=/opt/nexoda-barber1
```
База у каждого своя (`data/nexoda.db` внутри папки) — данные не пересекаются.

## Обновление кода
```bash
cd /opt/nexoda
# замени файлы новыми
systemctl restart nexoda
```

> Бэкап: периодически копируй файл `data/nexoda.db` каждого бота — там все записи и настройки.
