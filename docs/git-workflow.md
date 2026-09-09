# Git процесс ЛР1

Проект выполняется индивидуально. Исправление первой версии оформлено через [issue #1](https://github.com/FastGEUS/confmanager/issues/1), ветку lr1-fixes, восемь коммитов и [PR #2](https://github.com/FastGEUS/confmanager/pull/2). PR проверен самостоятельно и принят в main. Тег [v0.1.0](https://github.com/FastGEUS/confmanager/tree/v0.1.0) указывает на 53b3df5.

Текущее упрощение оформляется отдельно через [issue #3](https://github.com/FastGEUS/confmanager/issues/3) и ветку lr1-simple. Автотесты и инструменты качества перенесены в план ЛР3; для ЛР1 остаются команды и ручные сценарии из README.

## Конфликт слияния

Ветки lr1-fixes и demo/local-checks разошлись от be2eeeb. В demo/local-checks коммит 6898699 изменил строку проверки README на Make; в lr1-fixes коммит 8198bcf изменил ту же строку на команду Python. Слияние остановилось:

```text
Auto-merging README.md
CONFLICT (content): Merge conflict in README.md
Automatic merge failed; fix conflicts and then commit the result.
UU README.md
```

Конфликт разрешён объединением обеих инструкций. Создан настоящий merge-коммит e6edd214374a1867292fb24f30199c6755ca13f8 с двумя родителями. Проверить историю можно командами:

```bash
git show --format=fuller --no-patch e6edd21
git log --graph --oneline --all
```

Сам конфликт и его разрешение сохранены в истории, даже если текущая инструкция проверки изменяется.

## Даты

Даты новых коммитов вручную установлены на 8–9 сентября 2026 года по запросу владельца. Фактическая работа и публикация выполнены 5 октября; issue и PR сохраняют реальные даты. Исходная история и опубликованный тег не переписываются.
