# Technical evidence

The final project archive was reopened from the original authenticated course
submission on November 8, 2026. The original final report and readable source
files were reviewed separately from the older preparation notes.

## Source inventory

[Source fingerprints](source_inventory.json) identify the original ZIP, packaged
workbook, Prep workbook/flow, CSV, extract and PDF. The public repository excludes
account IDs, private source paths, grades and feedback.

[Original workbook XML](../tableau/original_workbook.twb) is copied from the final
TWBX as source evidence. Its readable connections use a relative Hyper location.
The extract is not supplied, so this is not a portable packaged application.

## Final workbook

The [workbook inventory](workbook_inventory.json) records ten worksheets and one
dashboard. Seven distinct sheets appear on the dashboard: title salaries, employee
geography, company-size distribution, time trend, average-salary KPI,
country-count KPI and record-count KPI. Three additional worksheet definitions
remain in the file without being placed on the dashboard.

The complete [visual gallery](../FIGURE_GALLERY.md) separates the original
final-report image from cached source thumbnails. These are saved visuals, not
new runtime screenshots.

## Recovered Prep logic

The [sanitized transformations](../prep/transformations.json) preserve the
ordered renames, added columns, null filters and two remap dictionaries.
[Calculated fields](../prep/calculated_fields.txt) preserve the three recovered
IF/CASE definitions. Source/output file paths and internal document identifiers
are omitted. No deduplication or outlier-removal operation was recovered.

The original final workbook additionally declares a Salary (USD) bin of 20,000.
The three label/flag formulas above belong to Prep, not to explicit workbook
calculated fields.

## Reproduction and evidence classes

The [salary audit](../scripts/analyze_salaries.py) recomputes raw counts and group
summaries from the public CSV. Its [results](data_validation.json) distinguish
raw-title statistics from the saved remapped dashboard groups. The new source
extractor reads authorized copies of the original ZIP/XML/flow structures and
emits selected evidence without executing Tableau expressions.

Both helpers and their synthetic tests are new November 2026 portfolio work.
They do not establish an original 2025 Python implementation, refresh the Hyper
extract or demonstrate fresh Tableau interactions.

## Remaining verification

The [November 10 submission recheck](submission_recheck_2026-11-10.json) confirms
that the reopened original final attachments match the retained fingerprints.
Rerunning the static exporter reproduced the published TWB and selected Prep
evidence; rerunning the public CSV audit reproduced its saved aggregate JSON.
The new readable SVG is a separate Python review view. These checks do not execute
Tableau or replace the native-runtime steps below.

1. Reconnect the data and open the workbook in Tableau.
2. Run the recovered Prep flow in an authorized environment and compare output with source records.
3. Confirm dashboard filters/actions and save a new readable export.
4. Correct geography labels, the high-paying display name, crowded legends and salary-axis typo in that new version.

Those steps have not been completed during this source-publication audit.
