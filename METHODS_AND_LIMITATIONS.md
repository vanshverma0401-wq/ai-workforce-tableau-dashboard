# Methods and limitations

## Evidence versions

The final submission contains a packaged workbook, a Prep folder, source CSV,
Hyper extract and final PDF. The final TWBX has ten worksheets and one dashboard;
the older six-worksheet preparation record does not describe this final version.
The public workbook XML is the actual final source, not a newly invented Tableau
implementation. Hashes identify the inspected originals.

The Prep evidence and worksheet inventory are selected static exports. New Python
checks were added in November 2026, separate from the 2025 team project.

## Dataset grain and scope

The CSV contains 637 submitted salary records, 11 columns and 50 raw job titles.
Work-year counts are 73, 217 and 347 for 2020, 2021 and 2022 respectively.
The fields include employment and experience codes, salary/currency/USD values,
remote ratio, employee residence, company location and company size. No names or
contact details are present in this public file.

These anonymous submissions form a convenience sample. Different role, geography,
experience and employer composition affect group means. The sample does not
establish representative worldwide salary levels, causal effects, current job
availability, regional growth or an explanation based on the pandemic.

## Repeated records and cleaning

There are 588 distinct complete rows and 49 additional repeated-row occurrences.
No row identifier establishes whether a repeated record is erroneous. The public
audit retains every raw row and reports the repetition count.

The saved Prep logic contains 11 renames, three added columns, two salary-null
filters and two job-title remap steps. No deduplication, general datatype-change
or outlier-removal node was recovered. The raw file has no empty fields or invalid
numeric salary values. The final write-up's stronger cleanup claims are not
repeated as verified implementation.

## Derived fields and grouping

The recovered formulas label remote ratios 100 as Remote, 50 as Hybrid, and the
remaining branch as On-site. Experience codes EN/MI/SE/EX become Entry-Level,
Mid-Level, Senior and Executive. The high-paying flag is inclusive at $200,000,
although its original display name says greater than $200,000.

Two sequential remap dictionaries change the meaning of role groups. Examples
include Manager to Engineer to ML Engineer and Data Scientist to Applied Data
Scientist. This reduces 50 raw titles to 40 grouped labels in a static application
of the saved dictionaries. These project-specific groupings are not a claim that
the merged roles are professionally equivalent. Raw-title audit summaries remain
separate from grouped dashboard output.

## Chart and KPI semantics

- Country map: Employee Country, derived from employee residence. Its worksheet name referring to company location is misleading.
- Country KPI: distinct Employee Country count; 59 raw residence codes versus 52 company-location codes.
- Box plot: Company Size, despite the worksheet's experience-level name.
- Average salary KPI: AVG of Salary (USD), not median or an estimate for an individual.
- Record KPI: COUNT of the job-title field, not an independently verified count of unique people or job openings.
- Time plot: calendar work year within 2020-2022. Sample composition differs by year.
- Role bar chart: grouped titles and saved filter context; raw unfiltered rankings can differ.

Company-size means and medians need not have the same ordering. For example, the
raw medium-company median exceeds the large-company median in this snapshot;
therefore the original report's broad larger-companies-pay-more narrative needs
qualification.

## Visual and runtime boundaries

The dashboard image is the saved final-report figure. The source thumbnails are
cached workbook views. Original crowded labels, truncated legend entries and a
salary-axis typo are preserved rather than silently described as corrected.
The map attribution embedded in the original image remains intact.

Source XML establishes seven placed sheets, five filter controls and three saved
on-select filter actions. This does not prove their behavior in a fresh session.
No Tableau Desktop/Prep open, extract execution, refresh or new export was
performed during publication. The Hyper database was not opened or decoded.

The public TWB still references its original relative Hyper location, which is
not distributed. It is source evidence, not a self-contained working package.
Configure authorized data connections and validate the flow before a runtime claim.

## Reproduction

### November 2026 readable review export

`scripts/render_review.py` creates `assets/review/salary-overview.svg` from the
public raw CSV through the existing aggregate audit. It shows the raw-record
overall mean, group means with their valid-salary denominators, employee-residence
code count and yearly sample counts. It retains repeated rows and does not apply
the original Prep title remaps or saved dashboard filters. XML text is escaped,
nonfinite/negative metrics are rejected, and source/output collisions are refused.

This new graphic resolves readability and labeling in a separate independent
view. The original Tableau dashboard and thumbnails stay unchanged. No native
Tableau/Prep execution, Hyper refresh or interactive filter validation has been
performed. A source recheck of the actual final attachments on November 10 matched
the source inventory and the public TWB/Prep evidence byte-for-byte.

The public raw CSV, exact attribution and Python audit allow readers to reproduce
counts and raw aggregate findings freely. They do not reproduce Tableau's filter
context, saved extract state or a loadable packaged workbook. Detailed source
logic remains available for independent review and a future controlled rebuild.
