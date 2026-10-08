# ЛР2. Результаты развёртывания и испытаний ConfManager

Проверки выполнены владельцем проекта на двух VM VMware 6–8 октября 2026 года. Запись составлена по присланному выводу команд и сообщениям о работе интерфейса. Это результаты учебного стенда, а не протокол приёмки преподавателем.

Задача: [#5](https://github.com/FastGEUS/confmanager/issues/5). Изменения: [PR #6](https://github.com/FastGEUS/confmanager/pull/6), ветка lr2-deploy.

## Стенд и проверенная версия

| Параметр | Фактическое значение |
| --- | --- |
| Сервер приложения | app-srv, Host-only 192.168.142.10 |
| Сервер БД | db-srv, Host-only 192.168.142.11/24 на ens33 |
| Клиент | Windows, 192.168.142.1, VMnet1 |
| Интернет VM | Второй адаптер NAT; на db-srv ens37 с DHCP |
| СУБД | PostgreSQL 18.6; кластер 18 main, порт 5432 |
| БД и роль | confmanager, владелец postgres; приложение подключается как confuser |
| Python app-srv | 3.14.4 |
| Диск app-srv при установке | Корневой LV 8.1 ГБ, свободно 4.0 ГБ |
| Версия, установленная на VM | 24cbe5cbfe08e3a2524092819c39e65a646bde92 |
| Сервисный пользователь | confapp, UID 999, shell /usr/sbin/nologin |
| Исходники / окружение | /opt/confmanager/src и /opt/confmanager/.venv |
| Настройки | /etc/confmanager/app.env; значения секретов в эту запись не включены |

Точный выпуск ОС нужно перенести в итоговый отчёт из /etc/os-release. Инструкция предусматривает Ubuntu Server без GUI; вывод systemctl get-default в переданных результатах не представлен.

## Что проверено

| Проверка | Наблюдаемый результат |
| --- | --- |
| Подключение SQL с app-srv | current_user=confuser, current_database=confmanager |
| Ограничения роли | В выводе du нет SUPERUSER, CREATEDB, CREATEROLE; public даёт confuser USAGE/CREATE |
| Сетевое прослушивание БД | listen_addresses=localhost,192.168.142.11; ss показывает 127.0.0.1:5432 и 192.168.142.11:5432 |
| Установка приложения | setup_app.sh завершился; pip check: No broken requirements found; deployed.sha совпадает с проверенной версией |
| Внешние настройки и права | /etc/confmanager root:root 700; app.env root:root 600; src root:confapp 750 |
| Процесс приложения | После reboot MainPID=1244, User=confapp |
| Авторизация в интерфейсе | Владелец подтвердил создание оргкомитета, открытие страницы и успешный вход |
| SSH | Подключения с ключом работают; sshd -T: PermitRootLogin no, PasswordAuthentication no, KbdInteractiveAuthentication no, PubkeyAuthentication yes |
| Firewall app-srv | UFW active; SSH 22 и HTTP 8000 разрешены только от 192.168.142.1 к 192.168.142.10 |
| Firewall db-srv | UFW active; SSH 22 от 192.168.142.1; PostgreSQL 5432 от 192.168.142.10 |
| Доступ с Windows | TCP 22 обеих VM и TCP 8000 app-srv: True; TCP 5432 db-srv: False при доступном ping |
| Готовность с включённым firewall | GET /ready с app-srv: HTTP 200, status=ready |
| Аварийное завершение | SIGKILL основного процесса; PID 1224 сменился на 3274, NRestarts 0 → 1; журнал показывает повторный запуск через 5 секунд |
| Отказ PostgreSQL | После остановки БД /health=200, /ready=503, confmanager остаётся active |
| Восстановление БД | После запуска PostgreSQL /ready=200 без ручного перезапуска приложения |
| Изменение параметра службы | Drop-in изменил RestartUSec 5s → 10s; после удаления этого файла значение вернулось к 5s, /ready=200 |
| Перезагрузка двух VM | db-srv загрузился 08.10 в 14:11:08 UTC, app-srv в 14:11:46 UTC; PostgreSQL online, confmanager enabled/active |
| Сохранность данных | Владелец подтвердил, что тема поданной заявки сохранилась после reboot |
| Локальные файлы в Git | git ls-files .env app.env confmanager.db не вывел файлов |
| Исправление клона | Одинаковый machine-id заменён на db-srv; после reboot идентификаторы различаются, адрес .11 сохраняется, PostgreSQL online и /ready=200 |

Проверка sshd -T подтверждает эффективную конфигурацию. Отдельный вывод попыток запрещённого root-входа и парольного входа не предоставлялся. Проверка отсутствия трёх локальных файлов в Git не является автоматическим сканированием всей истории на секреты.

## Фрагменты вывода

До аварии и после автоматического восстановления:

```text
ActiveState=active
MainPID=1224
NRestarts=0

ActiveState=active
MainPID=3274
NRestarts=1
```

Во время отказа БД и после восстановления:

```text
GET /health → HTTP/1.1 200 OK
GET /ready  → HTTP/1.1 503 Service Unavailable
{"detail":"Database temporarily unavailable"}
systemctl is-active confmanager → active

GET /ready → HTTP/1.1 200 OK
{"status":"ready"}
```

Проверка systemd drop-in:

```text
DropInPaths=
RestartUSec=5s
RestartUSec=10s
RestartUSec=5s
```

После перезагрузки app-srv:

```text
enabled
active
MainPID=1244
User=confapp
HTTP/1.1 200 OK
{"status":"ready"}
```

Время в выводе VM и HTTP — UTC. Московское время отличается на +3 часа.

## Повторение и сдача

Команды подготовки и испытаний приведены в [lr2-deploy.md](lr2-deploy.md). Файлы deploy/ и код приложения в этом завершающем изменении не меняются: устанавливать новую версию ради добавления этой записи не требуется. SHA стенда остаётся указанным выше.

Для итогового отчёта нужны ФИО, группа, данные преподавателя, точный выпуск ОС, режим без GUI и реальные материалы стенда. Преподаватель отдельно принимает работу и проводит контрольные действия. Для защиты полезно дополнительно показать фактический отказ root/парольного SSH и повторить пользовательский сценарий с назначением и оплатой оргвзноса; полный сценарий оплаты на PostgreSQL 18 в присланных результатах не зафиксирован.

Пароли, JWT, приватные SSH-ключи, реальные значения app.env и полные machine-id в документацию не включаются.
