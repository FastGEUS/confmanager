# ЛР2. Развёртывание ConfManager на двух Linux-машинах

Рабочая инструкция для нового стенда VMware. Задача: [issue #5](https://github.com/FastGEUS/confmanager/issues/5), ветка `lr2-deploy`. Развёртывание и основные испытания выполнены на VM 6–8 октября 2026 года; фактические результаты приведены в [записи испытаний](lr2-results.md). ЛР2 требует Debian-like ОС без GUI, две машины, SSH по ключам, права, PostgreSQL, systemd, firewall и повторяемое развёртывание без контейнеров.

## 1. Создание VM — первый этап

Использовать Ubuntu **Server** 24.04 LTS amd64: [официальный ISO](https://releases.ubuntu.com/24.04/). Desktop и графическую среду не устанавливать. Создать две независимые VM; клонирование не требуется.

| Параметр | Сервер приложения | Сервер БД |
| --- | --- | --- |
| Имя VM / hostname | app-srv | db-srv |
| CPU, стартовая конфигурация | 2 vCPU | 2 vCPU |
| RAM, стартовая конфигурация | 2 ГБ | 2 ГБ |
| Диск | 20 ГБ | 20 ГБ |
| Администратор | svet с sudo | svet с sudo |
| Сеть | Host-only + NAT | Та же Host-only + NAT |
| Плановый Host-only IP | 192.168.142.10/24 | 192.168.142.11/24 |

Ресурсы — предлагаемые для учебного стенда, а не требования методички. Обе VM должны работать одновременно. В VMware проверить наличие двух подключённых адаптеров: Host-only для связи с Windows и между VM, NAT для установки пакетов. Bridged для этого стенда не нужен.

В Virtual Network Editor проверить Host-only подсеть и диапазон DHCP. Адреса выше — пример: использовать их только если сеть действительно `192.168.142.0/24`, они свободны и исключены из выдачи DHCP. При другой подсети согласовать новые адреса и заменить их во всех командах, Netplan, PostgreSQL и app.env. Не менять общую сеть, от которой зависят другие VM, без проверки.

В установщике: стандартная Ubuntu Server, пользователь svet, OpenSSH Server включить, дополнительные server snaps не выбирать. На первом этапе оставить DHCP. После установки отключить ISO и перезагрузить. В консоли **каждой VM** выполнить:

```bash
hostnamectl
cat /etc/os-release
systemctl get-default
ip -br link
ip -br a
ip route
sudo -v
```

Ожидается `multi-user.target`; hostname и IP различаются. Сохранить вывод без паролей. В PowerShell Windows выполнить `ipconfig` и определить IPv4 адаптера VMware Host-only — он понадобится для SSH и firewall. На этом этапе не отключать парольный SSH и не включать firewall.


### Если db-srv создан клонированием app-srv

Фактический стенд получен клонированием. На клоне нужно изменить hostname и запись 127.0.1.1 в /etc/hosts, назначить отдельный статический Host-only IP, проверить MAC адаптеров и создать отдельные ключи SSH-сервера. Выполнять в консоли VMware именно клона; не на app-srv.

Ключи сервера можно сохранить и пересоздать:

```bash
ssh_backup_dir=$(sudo mktemp -d /root/db-srv-ssh.XXXXXX)
sudo mv /etc/ssh/ssh_host_* "$ssh_backup_dir/"
sudo ssh-keygen -A
sudo sshd -t && sudo systemctl restart ssh
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Новый отпечаток сверяется в консоли VM перед принятием ключа на Windows. Старую запись удаляют только для адреса клона через ssh-keygen -R, не отключая проверку ключей.

Сравнить /etc/machine-id на обеих VM. Если они одинаковы, сначала убедиться через sudo netplan get, что Host-only адрес клона статический. Для фактического стенда /var/lib/dbus/machine-id уже был ссылкой на /etc/machine-id. На таком клоне выполнены:

```bash
sudo cp -a --update=none /etc/machine-id /root/db-srv-machine-id.before-lr2
new_id_file=$(mktemp)
systemd-id128 new > "$new_id_file" && sudo install -o root -g root -m 444 "$new_id_file" /etc/machine-id
rm "$new_id_file"
cat /etc/machine-id
```

Только после успешной замены идентификатора перезагрузить клон. Если D-Bus использует отдельный файл, сначала согласовать оба идентификатора; не применять этот блок вслепую. После reboot проверить новый machine-id, прежний Host-only IP, pg_lsclusters и /ready с app-srv. NAT-адрес по DHCP может измениться.

## 2. Постоянная адресация

Сначала по MAC в VMware определить, какой Linux-интерфейс относится к Host-only, а какой — к NAT. Имена `ens33` и `ens37` ниже только пример. Настраивать сеть из консоли VMware.

```bash
sudo ls -l /etc/netplan
sudo cat /etc/netplan/*.yaml
sudo mkdir -p /root/lr2-backup
sudo cp -a /etc/netplan /root/lr2-backup/netplan-before
```

Редактировать существующий файл Netplan, проверив остальные YAML на пересекающиеся настройки. Пример для app-srv:

```yaml
network:
  version: 2
  renderer: networkd
  ethernets:
    ens33:
      dhcp4: false
      addresses: [192.168.142.10/24]
    ens37:
      dhcp4: true
```

На db-srv Host-only адрес — `.11/24`. На Host-only не добавлять default gateway. Подставить фактический путь файла вместо FILE:

```bash
sudo chmod 600 FILE
sudo netplan generate
sudo netplan try
```

Подтвердить рабочую конфигурацию в течение таймера. Проверить `ip -br a`, `ip route`, ping между VM, `getent hosts github.com` и выход в интернет через NAT. У обеих VM постоянный адрес должен быть на одном Host-only сегменте.

## 3. SSH по ключам

Windows PowerShell: создать отдельный ключ, если этого файла ещё нет. Приватный ключ не отправлять и не добавлять в Git. Для обоих серверов сверить отпечаток с `sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` в консоли соответствующей VM.

```powershell
ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\lr2_ed25519" -C "svet-lr2"
Get-Content "$env:USERPROFILE\.ssh\lr2_ed25519.pub" | ssh svet@192.168.142.10 "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
Get-Content "$env:USERPROFILE\.ssh\lr2_ed25519.pub" | ssh svet@192.168.142.11 "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys"
ssh -i "$env:USERPROFILE\.ssh\lr2_ed25519" -o IdentitiesOnly=yes -o PasswordAuthentication=no svet@192.168.142.10
ssh -i "$env:USERPROFILE\.ssh\lr2_ed25519" -o IdentitiesOnly=yes -o PasswordAuthentication=no svet@192.168.142.11
```

Только после успешного входа по ключу на **обе VM**, сохранив рабочую сессию и доступ к консоли:

```bash
sudo tee /etc/ssh/sshd_config.d/00-lr2.conf >/dev/null <<'EOF'
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
EOF
sudo sshd -t
sudo systemctl reload ssh
sudo sshd -T | grep -E 'permitrootlogin|passwordauthentication|kbdinteractiveauthentication|pubkeyauthentication'
```

Ожидается no/no/no/yes. Если отличается — проверить Include, Match и другие snippets; при Match использовать `sshd -T -C` для реального клиента. Повторно проверить вход по ключу; root-вход и вход с `-o PubkeyAuthentication=no` должны отказать. Пароль sudo сохраняется.

## 4. PostgreSQL — db-srv

```bash
sudo apt update
sudo apt install -y postgresql
pg_lsclusters
sudo -u postgres psql -Atc 'SHOW config_file;'
sudo -u postgres psql -Atc 'SHOW hba_file;'
```

Записать фактическую версию и имя кластера. Не угадывать их по версии Ubuntu. Файл `deploy/create_database.sql` выполнить один раз через `sudo -u postgres psql -v ON_ERROR_STOP=1 -f /путь/create_database.sql` или выполнить его команды в интерактивном psql. Пароль задаётся скрытым запросом `\password`; он не содержится в SQL-файле. При повторе сначала проверить `\du` и `\l`, не удалять существующую БД.

Роль confuser имеет CONNECT к выделенной БД и USAGE/CREATE в public, потому что текущая версия создаёт начальные таблицы при запуске. Она не владеет самой БД и не имеет SUPERUSER, CREATEDB, CREATEROLE или REPLICATION. Разделение создания схемы и runtime-роли можно выполнить вместе с миграциями в ЛР3.

Сохранить копии конфигураций в `/root/lr2-backup/`. В postgresql.conf установить:

```text
listen_addresses = 'localhost,192.168.142.11'
password_encryption = 'scram-sha-256'
```

В pg_hba.conf **перед существующими host-правилами** добавить:

```text
host confmanager confuser 192.168.142.10/32 scram-sha-256
host all all 0.0.0.0/0 reject
host all all ::0/0 reject
```

Локальные `local`-правила сохранить: администрирование выполняется через Unix socket (`sudo -u postgres psql` без `-h`). Этот блок разрешает TCP к заданной БД только app-srv; остальные TCP-подключения, включая localhost, отклоняются. Повторно одинаковый блок не добавлять. PostgreSQL использует первое подходящее правило; более ранние широкие разрешения нужно устранить.

```bash
sudo -u postgres psql -c "SELECT line_number,error FROM pg_hba_file_rules WHERE error IS NOT NULL;"
# Заменить VERSION и CLUSTER значениями pg_lsclusters.
sudo pg_ctlcluster VERSION CLUSTER restart
sudo ss -tlnp | grep 5432
```

Ошибок pg_hba быть не должно; порт слушает localhost и Host-only, не NAT-интерфейс. На app-srv установить `postgresql-client` и проверить:

```bash
psql -h 192.168.142.11 -U confuser -d confmanager -W -c 'SELECT current_user, current_database();'
```

## 5. Код и установка — app-srv

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip postgresql-client
python3 --version
```

Получить репозиторий под svet. Для приватного репозитория использовать отдельный read-only deploy key GitHub, принадлежащий svet, а не confapp. Создать его через `ssh-keygen -t ed25519 -f ~/.ssh/confmanager_deploy`; добавить публичный ключ в Settings → Deploy keys без Allow write access. При passphrase загрузить ключ в ssh-agent. Сверить GitHub host key по [официальной документации](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints).

```bash
GIT_SSH_COMMAND="ssh -i $HOME/.ssh/confmanager_deploy -o IdentitiesOnly=yes" git clone git@github.com:FastGEUS/confmanager.git ~/confmanager-lr2
cd ~/confmanager-lr2
git switch lr2-deploy
git status --short
git rev-parse HEAD
sudo bash deploy/setup_app.sh "$PWD"
```

Для итогового развёртывания выбрать проверенный SHA, записать его в отчёт. Скрипт копирует только Git-версию через archive, создаёт confapp с nologin, venv и службу. Исходники и venv принадлежат root:confapp: служба читает код, но не меняет его. `.git`, SSH-ключ и локальная `.env` не переносятся. Скрипт **не запускает** службу и не создаёт секреты автоматически.

Повторная установка того же SHA разрешена после `sudo systemctl stop confmanager`. Другой SHA не перезаписывается: сначала остановить службу, сохранить старые src, venv и deployed.sha вне /opt/confmanager, затем разместить новую версию на освободившихся путях и повторить установку. Существующую БД и `/etc/confmanager/app.env` сохранять. Для отката вернуть сохранённые пути на прежние места и запустить службу; не копировать venv на другой путь для запуска.

## 6. Конфигурация и запуск

```bash
sudo install -o root -g root -m 600 deploy/app.env.example /etc/confmanager/app.env
sudo nano /etc/confmanager/app.env
```

При повторной настройке редактировать существующий файл, не копировать шаблон поверх него. Вписать реальные Host-only IP, пароль confuser и случайный SECRET_KEY, сгенерированный локально через `python3 -c 'import secrets; print(secrets.token_hex(32))'`. Если пароль БД содержит `@`, `:`, `/`, `%` и другие специальные символы, URL-encode его при записи DATABASE_URL. Файл — синтаксис EnvironmentFile, не shell-скрипт; не использовать `source` и shell-подстановки. Не выводить реальные секреты в отчёт.

Доступ к `/etc/confmanager/` имеет root; systemd читает файл и передаёт переменные процессу confapp. `CONFMANAGER_ENV_FILE=` в unit отключает чтение `.env` из исходников. `connect_timeout=5` ограничивает ожидание нового соединения с БД.

```bash
sudo systemctl enable --now confmanager
systemctl is-enabled confmanager
systemctl is-active confmanager
sudo journalctl -u confmanager -n 40 --no-pager
curl --fail http://192.168.142.10:8000/ready
```

Создать оргкомитет существующей командой приложения; transient-служба получает ту же конфигурацию, пароль вводится скрыто:

```bash
sudo systemd-run --unit=confmanager-bootstrap --wait --collect --pty \
  -p User=confapp -p Group=confapp \
  -p WorkingDirectory=/opt/confmanager/src \
  -p EnvironmentFile=/etc/confmanager/app.env \
  -p Environment=CONFMANAGER_ENV_FILE= \
  /opt/confmanager/.venv/bin/python -m app.manage create-committee --email committee@example.org
```

Штатное управление: `sudo systemctl start confmanager`, `stop`, `restart`, `status`. `Restart=on-failure` восстанавливает процесс после аварии, а не после намеренного stop. `StartLimitIntervalSec=0` позволяет повторять попытки запуска, если удалённая БД ещё не поднялась. Логи находятся в journal; исходники доступны только для чтения через ProtectSystem=strict, Home скрыт, процесс не получает новые привилегии.

## 7. Firewall — обе VM

В PowerShell определить реальный Windows Host-only IPv4 через `ipconfig`. В командах **заменить HOST_IP** этим адресом. Выполнять из консоли VMware или с сохранённой рабочей сессией. Сначала разрешить SSH, потом включить UFW.

app-srv:

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from HOST_IP to 192.168.142.10 port 22 proto tcp
sudo ufw allow from HOST_IP to 192.168.142.10 port 8000 proto tcp
sudo ufw status numbered
sudo ufw enable
```

db-srv:

```bash
sudo apt install -y ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from HOST_IP to 192.168.142.11 port 22 proto tcp
sudo ufw allow from 192.168.142.10 to 192.168.142.11 port 5432 proto tcp
sudo ufw status numbered
sudo ufw enable
```

Проверить существующие широкие allow-правила, включая IPv6: default deny их не отменяет. Удалять только установленные лишние правила, не сбрасывать firewall целиком. С app-srv SQL-запрос должен работать; с Windows `Test-NetConnection 192.168.142.11 -Port 5432` должен дать False. На Windows доступны SSH обеих VM и HTTP app-srv; NAT-порты приложения и БД не открываются.

## 8. Проверки для защиты

Каждый результат записывать после фактической проверки, приложив вывод или скриншот без секретов.

- **Сценарий:** открыть `http://192.168.142.10:8000/`, зарегистрировать участника, войти и подать заявку; оргкомитет назначает взнос, попытка оплаты new отказывает, accepted оплачивается. Второй участник не видит чужую заявку; административное действие с его токеном возвращает 403.
- **Перезагрузка:** reboot обеих VM; после загрузки проверить enabled/active, `/ready`, интерфейс и сохранённую заявку. Не считать systemd unit postgresql само по себе доказательством работающего кластера: проверить pg_lsclusters.
- **Авария:** записать `systemctl show confmanager -p MainPID`; выполнить `sudo systemctl kill --kill-whom=main --signal=SIGKILL confmanager`; через 7 секунд показать новый MainPID, `NRestarts`, active и журнал. Штатный stop не должен восстанавливать службу.
- **Отказ БД:** на db-srv `sudo pg_ctlcluster VERSION CLUSTER stop`. На app-srv `/health` может остаться 200 (процесс жив), `/ready` и операции с БД должны вернуть 503. Сохранить `curl -i` и journal. Вернуть БД командой start; проверить восстановление `/ready` и сценария без потери данных. Если повторные попытки запуска были ограничены внешним drop-in, изучить его и выполнить `systemctl reset-failed` перед restart.
- **Процесс, порт, журнал:** `systemctl show confmanager -p User -p MainPID`, `ps -eo user,pid,args`, `sudo ss -tlnp`, `sudo journalctl -u confmanager -n 40`. Процесс под confapp, не root; порты 8000/5432 только на ожидаемых интерфейсах.
- **Параметр службы:** создать отдельный `/etc/systemd/system/confmanager.service.d/lr2-demo.conf` с `[Service]` и `RestartSec=10`. daemon-reload/restart; `systemctl show confmanager -p RestartUSec` показывает 10s. Удалить только этот drop-in, повторить reload/restart — 5s.
- **Сеть:** Windows не подключается к TCP 5432, app-srv выполняет SQL. Отказ SQL-аутентификации не заменяет проверку закрытого TCP-порта.
- **Права и Git:** `id confapp`, `getent passwd confapp`, `sudo stat -c '%U:%G %a %n' /opt/confmanager/src /etc/confmanager /etc/confmanager/app.env`; `git ls-files .env app.env confmanager.db` пуст. Пароли, токены, приватные ключи и локальную БД в Git не добавлять.

## 9. Повторяемость, PR и отчёт

Обязательные проверки изменения: `bash -n deploy/setup_app.sh`, `git diff --check`, команды и сценарии из README. Проверить diff на реальные секреты. Скрипт установки и SQL проверяются на VM до завершения ЛР2; проверка синтаксиса не заменяет развёртывание.

Все изменения через issue → ветку → осмысленные коммиты → PR → самостоятельный просмотр diff. Для этого стенда результаты испытаний уже записаны в [lr2-results.md](lr2-results.md); изменения проходят итоговый просмотр в [PR #6](https://github.com/FastGEUS/confmanager/pull/6). Отчёт и живая приёмка преподавателем оформляются отдельно. Для нового развёртывания повторить испытания, не считать результаты этого стенда автоматически действующими.

Отчёт: титульный лист по шаблону преподавателя, цель, конфигурация VM и фактические IP, SSH и пользователи, права, PostgreSQL, развёрнутый SHA и версии Python/зависимостей, systemd, firewall, результаты каждого испытания, ссылки на issue/PR. Файл по шаблону `LR2_Фамилия_Группа.docx`. Прикладывать реальные доказательства; неизвестные результаты не заполнять как успешные.

Основа: вкладка «ЛР2» методички, включая обновление 23.09.2026 «ОС без графического интерфейса». Справочные источники: [Ubuntu 24.04](https://releases.ubuntu.com/24.04/), [systemd.service](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html), [pg_hba.conf](https://www.postgresql.org/docs/current/auth-pg-hba-conf.html), [настройки соединений PostgreSQL](https://www.postgresql.org/docs/current/runtime-config-connection.html).
