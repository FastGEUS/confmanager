# Схема данных — ConfManager (ЛР1)

## Сущности и связи

```
Participant (1) ──── (N) Application (1) ──── (1) Fee
```

## Participant

| Поле | Тип | Описание |
|---|---|---|
| id | int, PK | Идентификатор |
| full_name | string | ФИО |
| email | string, unique | Email (используется для логина) |
| organization | string, nullable | Организация |
| role | string | Роль (по умолчанию "participant") |
| hashed_password | string | Хеш пароля |
| is_committee | bool | Признак члена оргкомитета |

## Application

| Поле | Тип | Описание |
|---|---|---|
| id | int, PK | Идентификатор |
| participant_id | int, FK → Participant.id | Автор заявки |
| topic | string | Тема доклада |
| status | enum | new / under_review / accepted / rejected |
| submitted_at | datetime | Дата подачи |

## Fee

| Поле | Тип | Описание |
|---|---|---|
| id | int, PK | Идентификатор |
| application_id | int, FK → Application.id, unique | Связанная заявка (1:1) |
| amount | float | Сумма оргвзноса |
| status | enum | unpaid / paid |
| paid_at | datetime, nullable | Дата оплаты |

## Бизнес-правило целостности

`Fee.status` может перейти в `paid` только если `Application.status == accepted`.
Проверка выполняется на уровне приложения (`app/crud.py::mark_fee_paid`), а не на уровне БД,
так как требует чтения связанной записи перед изменением.

## Дальнейшее расширение (следующие ЛР)

В теме 4 предусмотрены также сущности **Invitation** (приглашения), **Abstract** (тезисы) и
**HotelRequest** (потребность в гостинице) — добавляются на этапе работы с миграциями (ЛР3)
и очередями рассылки.
