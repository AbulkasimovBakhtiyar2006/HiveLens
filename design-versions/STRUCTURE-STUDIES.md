# HiveLens: twelve structure studies

Open http://127.0.0.1:8502/designs to compare. Atlas is now the main interface at `/`; the pre-study interface is preserved at `/?layout=classic`. Explicit `layout` links remain comparison previews. All twelve variants share the existing application, records, camera workflow and API. No dependency or additional model calls are introduced.

## 01 Focus

Reference: [Linear](https://linear.app/docs/projects)

Контекстная панель рядом с основным списком; подробности открываются по запросу.

Ульи в центре, важные проверки — в отдельной правой колонке. Компактная навигация и минимум визуальных рамок.

Local: http://127.0.0.1:8502/?layout=focus&palette=honey#overview

## 02 Registry

Reference: [Shopify Admin](https://shopify.dev/docs/api/app-home/latest/patterns/templates/resource-index)

Структура resource index: заголовок, основное действие, фильтры и таблица.

Единый реестр с поиском и фильтрами. Сводка компактная, проверки раскрываются отдельно, действия всегда у заголовка.

Local: http://127.0.0.1:8502/?layout=registry&palette=honey#overview

## 03 Panorama

Reference: [Stripe Dashboard](https://docs.stripe.com/dashboard/basics)

Обзор из отдельных модулей: показатели → контекст → подробные данные.

Самостоятельные карточки показателей, пространственная карта пасеки и панель проверок. Список ульев расположен ниже.

Local: http://127.0.0.1:8502/?layout=panorama&palette=honey#overview

## 04 Notebook

Reference: [GitHub Primer](https://primer.style/product/components/page-layout/)

Глобальная навигация сверху, контекстная панель сбоку, основное содержимое отдельно.

Разделы вынесены в верхние вкладки. Слева остаются только пасеки, справа — спокойная рабочая страница.

Local: http://127.0.0.1:8502/?layout=notebook&palette=honey#overview

## 05 Triage

Reference: [Sentry](https://sentry.io/changelog/new-issue-details-ui-now-available/)

Отдельная зона действий, выраженная иерархия, второстепенные детали свёрнуты.

Узкая колонка статусов и очередь ульев, требующих внимания. Полный реестр — сразу под ней. Тёмная навигация отделяет инструменты от данных.

Local: http://127.0.0.1:8502/?layout=triage&palette=honey#overview

## 06 Fieldbook

Reference: [Mailchimp](https://mailchimp.com/help/about-audience-analytics/)

Понятный обзор объектов, статусные группы и переход от сводки к конкретной записи.

У каждого улья своя карточка: состояние, источник и измерения рядом. Тёплая боковая панель и более свободная композиция.

Local: http://127.0.0.1:8502/?layout=fieldbook&palette=honey#overview

## Implementation

`layouts.js` moves existing nodes, retaining IDs and event delegation. `layouts.css` is scoped to the validated `data-layout` attribute. Map/weather panels use native details. Fieldbook preserves all table data and adds visual labels via a child-list observer only on the hive rows. Selection is URL-only and never changes the default layout. The gallery uses twelve local screenshots rather than running six background applications.


# Second set

## 07 Board

Reference: [Trello](https://support.atlassian.com/trello/docs/using-trello/)

Колонки и карточки Trello адаптированы под измеренные статусы. Статус определяется измерениями.

Ульи распределены по колонкам Critical, Watch, Normal и No data. Видно, где скопились проблемы; фильтры работают внутри всей доски.

Local: http://127.0.0.1:8502/?layout=board&palette=honey#overview

## 08 Atlas

Reference: [ArcGIS](https://doc.arcgis.com/en/arcgis-online/get-started/get-started-with-mv.htm)

Карта как основная рабочая поверхность, инструменты на боковой панели и отдельный список объектов.

Большая схема пасеки, компактный реестр справа и узкая панель инструментов слева. Выбор пасеки вынесен над рабочей областью.

Local: http://127.0.0.1:8502/?layout=atlas&palette=honey#overview

## 09 Chronicle

Reference: [Basecamp](https://5.basecamp-help.com/article/1160-activity)

Хронологическая лента с группировкой по дате. В HiveLens показан последний осмотр каждого улья, полная история доступна в записи.

Последние осмотры сгруппированы по датам. Навигация расположена сверху, сводка — на полях журнала. Спокойная вёрстка с книжными заголовками.

Local: http://127.0.0.1:8502/?layout=chronicle&palette=honey#overview

## 10 Workbench

Reference: [Airtable](https://www.airtable.com/guides/collaborate/interface-designer-record-review)

Record review: список записей и панель выбранного объекта рядом.

Выбираешь улей слева — справа сразу появляются его статус и измерения. Можно быстро просмотреть несколько ульев, не переходя между страницами.

Local: http://127.0.0.1:8502/?layout=workbench&palette=honey#overview

## 11 Folio

Reference: [Notion](https://www.notion.com/help/views-filters-and-sorts)

Несколько представлений одной базы, фильтры и последовательное раскрытие свойств.

Три отдельных представления: ульи, сводка состояния, карта и погода. На экране только текущая задача, остальные данные доступны во вкладках.

Local: http://127.0.0.1:8502/?layout=folio&palette=honey#overview

## 12 Dispatch

Reference: [Asana](https://asana.com/inside-asana/manage-workflow-project-views)

Группированный список с отдельными секциями и действиями над конкретной записью.

У каждой пасеки свой раскрываемый раздел. В строках ульев видны источник, статус и четыре измерения; разделы можно сворачивать.

Local: http://127.0.0.1:8502/?layout=dispatch&palette=honey#overview

The second set is scoped in `layouts-next.css` and `layouts-next.js`. Board, Chronicle, Workbench and Dispatch derive their cards from the existing filtered rows using DOM cloning and textContent, preserving data labels and record actions. These are views of actual saved data. They do not introduce drag-to-change health, invented dates, new network requests or model runs.
