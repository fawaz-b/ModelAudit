# ModelAudit: TRIPOD+AI Framework: Scope, Extraction and Implementation

This document explains how ModelAudit's 14-item TRIPOD+AI subset was selected and translated into an executable framework. It is intended for developers, researchers and reviewers who need to understand what the application assesses, how its requirements were defined, and how the assessment logic works.

The machine-readable implementation lives in `backend/framework/tripod_ai_subset.json`. This document is its technical companion: it records the source material, explains the assessment approach and makes clear where ModelAudit follows published guidance versus where it has adopted an explicit implementation rule.

The selected items are **3b, 5a, 5b, 6a, 6b, 8a, 9b, 10, 11, 12e, 16, 18e, 18f and 23a**.

## 1. Source materials and extraction approach

The extraction was based on the published TRIPOD+AI statement and its accompanying Expanded Checklist. The aim was to identify the source wording and explanatory guidance for the selected items before translating them into a smaller, testable subset for the ModelAudit MVP.

Throughout this document, published requirements are distinguished from application-specific choices. This matters because the JSON contains both source-derived guidance and operational rules introduced to make automated, evidence-linked assessment possible.

- Collins GS, Moons KGM, Dhiman P, et al. TRIPOD+AI statement. BMJ 2024;385:e078378 (CC BY 4.0). Table 2 (27-item checklist, D / E / D;E markings).
- TRIPOD+AI Expanded Checklist (Explanation and Elaboration Light), version 7-February-2024, from tripod-statement.org (the official supplement to the BMJ paper).
- Cross-check: for all 14 selected items the checklist wording in the supplement is identical to Table 2 in the paper. One label differs: the section for item 16 is called Training versus evaluation in Table 2 and Development versus evaluation in the supplement. The item wording is the same.
- All 14 items map confidently to the official source.

### Scope and limitations

- The official expanded checklist provides explanatory bullet points rather than worked examples of sufficient and insufficient reporting. The examples included here were therefore written specifically for ModelAudit. They are synthetic illustrations, labelled as such in the JSON, and should not be presented or cited as examples published by TRIPOD+AI.
- The 2015 TRIPOD Explanation and Elaboration paper (Annals of Internal Medicine) contains published examples for the original TRIPOD items. It was available as background material through the TRIPOD website but was not reviewed as part of this extraction. No claims in this document therefore rely on examples from that paper.

### Distinguishing source guidance from ModelAudit decisions

- **Directly source-derived:** item identifiers, official item wording, section names, D;E applicability and source references.
- **Paraphrased source guidance:** `reporting_expectations` entries marked `[E&E]`.
- **ModelAudit interpretation:** entries marked `[INTERP]`.
- **ModelAudit implementation choices:** prompts, elements and required flags, evidence expectations, retrieval queries, common misinterpretations, item rules, synthetic examples and category definitions.

### Why the framework uses this structure

The framework retains the 12 proposed fields and adds several fields needed to support consistent assessment and traceability:

- `official_item_text` and `applies_to`: the judge needs the exact item to avoid drift, and the loader needs the D;E marking. Every one of the 14 items is D;E.
- `elements` (key, description, required, optional required_when): TRIPOD+AI items are compound (item 8a has about five parts). Judging one blob invites the model to say reported on a partial match. Element-level findings make the evidence auditable and let code derive the category deterministically.
- `item_rules`: explicit operational rules such as when an item is not applicable.
- `illustrative_examples`: kept in the data for tests and reviewer help, flagged synthetic. The recommended approach is to not put them in prompts at first (unresolved question 5).
- Top-level `judgement_scheme`, `global_rules`, `judge_prompt_template` and `field_provenance`: defined once, not repeated 14 times. `judgement_categories` stays per item as an allowed-values list, so an item can exclude or add not_applicable.
- The judgement scheme includes a sixth category, `author_stated_unavailable`. This keeps an explicit author acknowledgement that information is unknown, unavailable or irrelevant separate from a situation in which the information simply cannot be located in the paper. Treating those situations as equivalent would misrepresent what the authors reported.

## 2. The selected TRIPOD+AI items

The following sections separate two related tasks. First, they summarise what the official checklist and expanded guidance ask authors to report. They then describe how ModelAudit breaks each selected item into assessable elements and what evidence the system should look for.

The official wording and guidance are the source requirements. Element definitions, retrieval queries, required flags and item-specific rules are ModelAudit's implementation of those requirements; they are not additional official TRIPOD+AI checklist items.

### 2.1 What the published guidance asks authors to report

In the guidance bullets below, `[E&E]` = source, `[INTERP]` = mine. Official item wording is CC BY 4.0, given for identification.

#### T-3b: Introduction / Background

**Official item wording:** Describe the target population and the intended purpose of the prediction model in the context of the care pathway, including its intended users (e.g., healthcare professionals, patients, public)

**What the guidance asks authors to report (paraphrase):**

- [E&E] State who the target population is, for example an age group, a country or people with a specific disease.
- [E&E] State the intended purpose, including the clinical decision or guidance the model supports (such as referral for testing, admission, triage, starting treatment or changing lifestyle) and the point in the care pathway where it would be used.
- [E&E] State who the intended users are (healthcare professionals, patients, the public or others).

**Source reference:** TRIPOD+AI item 3b; Expanded Checklist p1

#### T-5a: Methods / Data

**Official item wording:** Describe the sources of data separately for the development and evaluation datasets (e.g., randomised trial, cohort, routine care or registry data), the rationale for using these data, and representativeness of the data

**What the guidance asks authors to report (paraphrase):**

- [E&E] Describe the source of data for model development and for evaluation, such as a randomised trial, cohort, registry or electronic routine healthcare records.
- [E&E] State whether existing data were used or new data were collected prospectively for this study.
- [E&E] Where existing data were collected for another purpose, give the rationale and comment on suitability and representativeness for the intended target population, particularly if data come from a different setting or country.
- [E&E] Describe sources separately for development and evaluation. If synthetic data were used, explain why and how they were created.
- [INTERP] A statement about representativeness may be a limitation or caveat as well as an affirmation.

**Source reference:** TRIPOD+AI item 5a; Expanded Checklist p2

#### T-5b: Methods / Data

**Official item wording:** Specify the dates of the collected participant data, including start and end of participant accrual; and, if applicable, end of follow-up

**What the guidance asks authors to report (paraphrase):**

- [E&E] Specify the start and end dates of the period for which participants or data were selected.
- [E&E] For prognostic models, report the date of end of follow-up.
- [INTERP] When development and evaluation data are separate, dates are expected for each.

**Source reference:** TRIPOD+AI item 5b; Expanded Checklist p2

#### T-6a: Methods / Participants

**Official item wording:** Specify key elements of the study setting (e.g., primary care, secondary care, general population) including the number and location of centres

**What the guidance asks authors to report (paraphrase):**

- [E&E] Describe the healthcare setting and where participants were recruited from.
- [E&E] Report the geographical location, at a minimum the country, and the centres including the number of centres.
- [INTERP] For non-centre-based sources such as national household surveys, a centre count may not be meaningful.

**Source reference:** TRIPOD+AI item 6a; Expanded Checklist p2

#### T-6b: Methods / Participants

**Official item wording:** Describe the eligibility criteria for study participants

**What the guidance asks authors to report (paraphrase):**

- [E&E] Report the eligibility criteria so that readers can judge applicability and generalisability of the model.
- [E&E] This includes any restriction of continuous variables, for example the age range used to define eligibility.

**Source reference:** TRIPOD+AI item 6b; Expanded Checklist p2-3

#### T-8a: Methods / Outcome

**Official item wording:** Clearly define the outcome that is being predicted and the time horizon, including how and when assessed, the rationale for choosing this outcome, and whether the method of outcome assessment is consistent across sociodemographic groups

**What the guidance asks authors to report (paraphrase):**

- [E&E] For diagnostic models, define the outcome clearly, including whether a widely accepted reference standard was used.
- [E&E] For prognostic models, report the time horizon of prediction and the frequency of outcome assessment during follow-up.
- [E&E] If standard definitions such as ICD codes are used, state and reference them.
- [E&E] Report any discrepancies in outcome assessment across sociodemographic groups.
- [E&E] Where needed, confirm that no predictors were used to define the outcome or act as a proxy for it.
- [INTERP] The rationale and the sociodemographic consistency statement are part of the official item wording but are treated as non-required elements in the MVP so that the category stays informative.

**Source reference:** TRIPOD+AI item 8a; Expanded Checklist p3

#### T-9b: Methods / Predictors

**Official item wording:** Clearly define all predictors, including how and when they were measured (and any actions to blind assessment of predictors for the outcome and other predictors)

**What the guidance asks authors to report (paraphrase):**

- [E&E] Define all predictors included in the modelling, with units of measurement and all categories for categorical predictors, so others can replicate, implement or evaluate the model.
- [E&E] Describe how and when predictor values were measured. Predictors should be measured before or at the time the model is intended to be used.
- [E&E] Report actions to blind predictor assessment to other predictors and, for diagnostic models, to the outcome.
- [E&E] When there are very many predictors, a full list in supplementary material is acceptable if all are still clearly defined.

**Source reference:** TRIPOD+AI item 9b; Expanded Checklist p4

#### T-10: Methods / Sample size

**Official item wording:** Explain how the study size was arrived at (separately for development and evaluation), and justify that the study size was sufficient to answer the research question. Include details of any sample size calculation

**What the guidance asks authors to report (paraphrase):**

- [E&E] Describe how sample size was determined, separately for development and for evaluation, whether data were collected prospectively or already existed.
- [E&E] Give details and all estimates used in any sample size calculation.
- [E&E] If no formal calculation was done, for example because all available data were used, justify why the size was sufficient to answer the research question.

**Source reference:** TRIPOD+AI item 10; Expanded Checklist p5

#### T-11: Methods / Missing data

**Official item wording:** Describe how missing data were handled. Provide reasons for omitting any data

**What the guidance asks authors to report (paraphrase):**

- [E&E] Report, for each predictor considered, the number of missing values.
- [E&E] Report how missing values were handled, including assumptions about why they were missing.
- [E&E] If individuals or predictors were omitted because of missing values, report this and give reasons.
- [E&E] If values were imputed, give full details of the imputation method and confirm it was done separately for training and test data.

**Source reference:** TRIPOD+AI item 11; Expanded Checklist p5

#### T-12e: Methods / Analytical methods

**Official item wording:** Specify all measures and plots used (and their rationale) to evaluate model performance (e.g., discrimination, calibration, clinical utility) and, if relevant, to compare multiple models

**What the guidance asks authors to report (paraphrase):**

- [E&E] Report all measures used to evaluate model performance. As a minimum, discrimination and calibration (including calibration plots) are generally expected.
- [E&E] For time-to-event outcomes, describe how censoring and any competing risks were handled.
- [E&E] For prognostic models, report all time points at which performance was evaluated.
- [E&E] Report the methods used for graphical displays such as calibration plots with smooth curves and decision curves.
- [E&E] If models are compared, explain the comparison methods and the criteria for judging one superior.

**Source reference:** TRIPOD+AI item 12e; Expanded Checklist p7

#### T-16: Methods / Development versus evaluation

**Official item wording:** Identify any differences between the development and evaluation data in healthcare setting, eligibility criteria, outcome, and predictors

**What the guidance asks authors to report (paraphrase):**

- [E&E] Models developed in one setting, centre or country are not necessarily useful in another. Eligibility criteria, outcome and predictor definitions may differ between data sources.
- [E&E] Describing differences between development and evaluation data helps readers interpret performance and generalisability.
- [INTERP] An explicit statement that there are no differences in a given domain counts as addressing it.

**Source reference:** TRIPOD+AI item 16; Expanded Checklist p9

#### T-18e: Open science / Data sharing

**Official item wording:** Provide details of the availability of the study data

**What the guidance asks authors to report (paraphrase):**

- [E&E] Give details of availability of the study data, including where they can be found (repository, URL or DOI), how they can be retrieved, and any conditions or restrictions on use.
- [E&E] A data dictionary should accompany any shared data.
- [E&E] If data cannot be shared, give reasons.
- [E&E] Avoid platitudes such as data available upon reasonable request without stating what counts as a reasonable request.

**Source reference:** TRIPOD+AI item 18e; Expanded Checklist p10

#### T-18f: Open science / Code sharing

**Official item wording:** Provide details of the availability of the analytical code

**What the guidance asks authors to report (paraphrase):**

- [E&E] Give all details on availability of the analytical code, including documentation on how to run it, where it can be found, how to retrieve it, and any conditions or licences, with version.
- [E&E] Analytical code means all code needed in principle to replicate the reported results, including data cleaning.
- [E&E] Report the software and packages needed to reproduce the findings, with version numbers; more computing environment detail may be needed in some cases.

**Source reference:** TRIPOD+AI item 18f; Expanded Checklist p10

#### T-23a: Results / Model performance

**Official item wording:** Report model performance estimates with confidence intervals, including for any key subgroups (e.g., sociodemographic). Consider plots to aid presentation

**What the guidance asks authors to report (paraphrase):**

- [E&E] Present estimates of all performance measures described in item 12e, with confidence intervals.
- [E&E] Report estimates for the overall population and for any key groups of interest, for example sex or ethnicity, with confidence intervals.
- [E&E] Consider plots such as calibration plots with smooth curves and decision curves.
- [E&E] Report estimates for all evaluations undertaken (development data, evaluation data, internal validation) and at each time point for prognostic models.
- [E&E] Clearly indicate which data were used for each estimate.

**Source reference:** TRIPOD+AI item 23a; Expanded Checklist p12

### 2.2 How ModelAudit assesses each item

In the element lists below, required elements are in **bold**. Conditions in parentheses are `required_when` conditions.

#### T-3b

**Elements judged:**

- **target_population**
- **intended_purpose_and_pathway_position**
- **intended_users**

**Evidence a reviewer should look for:**

- A passage naming the population the model is meant for.
- A passage naming the decision or purpose and the pathway position.
- A passage naming the intended users.

**Retrieval queries:**

- intended use of the prediction model in the clinical pathway
- target population for which the model is intended
- intended users clinicians patients decision support
- model to support triage referral admission or treatment decision

**Misinterpretations that mislead an LLM:**

- The study sample described in Methods is not automatically the target population. Accept it only if the text says the model is intended for that population.
- General motivation such as improving outcomes is not an intended purpose unless a decision or use is named.
- A future-use statement in the Discussion can count only if it is explicit about decision, pathway position or users. Record which element it covers.
- A tool or app name does not show who the intended users are.

**Item rules:** none

#### T-5a

**Elements judged:**

- **data_source_type**
- **rationale_or_representativeness**
- existing_or_prospective
- **separate_for_development_and_evaluation** (if study has separate development and evaluation datasets)
- **synthetic_data_details** (if synthetic data were used)

**Evidence a reviewer should look for:**

- A passage naming the design or origin of each dataset.
- A passage justifying the data or discussing representativeness for the target population.
- For studies with separate development and evaluation data, a source description for each.

**Retrieval queries:**

- data source cohort registry survey electronic health records
- study design and data collection
- representativeness of the data for the target population
- external evaluation dataset source

**Misinterpretations that mislead an LLM:**

- Naming a dataset (for example a survey acronym) without saying what kind of data source it is gives only part of the first element.
- Representativeness concerns the target population, not sample size.
- Evaluation data may be described only in Results or a later Methods subsection. Search both.
- If one dataset is used for both development and internal evaluation, separate descriptions are not required, but the dataset must be described.

**Item rules:**

- If the study uses a single dataset with no separate evaluation dataset, do not require separate sources. Mark separate_for_development_and_evaluation as not_applicable.

#### T-5b

**Elements judged:**

- **collection_start_and_end**
- **end_of_follow_up** (if model is prognostic)
- **dates_for_each_dataset** (if study has separate development and evaluation datasets)

**Evidence a reviewer should look for:**

- A passage with a start and an end for the data collection or selection period.
- For prognostic models, a passage giving when follow-up ended.

**Retrieval queries:**

- participants were enrolled between
- data were collected from January to December
- study period start and end dates
- end of follow-up date

**Misinterpretations that mislead an LLM:**

- Publication date, access date or database extraction date is not the data collection period.
- A single year is a start without an end. Look for a range.
- A follow-up duration (for example 28 days) is not a date of end of follow-up. Treat it as partial for the follow-up element.
- For repeated cross-sectional surveys, the survey years are the collection period.

**Item rules:**

- Accept year-level ranges as sufficient and record the granularity in the rationale (see unresolved question 2).

#### T-6a

**Elements judged:**

- **setting_type**
- **country_or_location**
- **number_of_centres** (if data were collected at identifiable centres)

**Evidence a reviewer should look for:**

- A passage naming the setting type.
- A passage naming the country or location of data collection.
- A passage giving the number of centres, or a statement that it was a single centre.

**Retrieval queries:**

- study setting primary care secondary care hospital community
- participants were recruited from centres in
- multicentre number of hospitals and country
- geographical location of the study

**Misinterpretations that mislead an LLM:**

- Author affiliations are not the study location.
- The word multicentre without a number gives only part of the centres element.
- A single centre named in the text counts as a centre count of one.
- The country of the original development cohort may differ from the country of the evaluation cohort. Judge the dataset the paper is describing.

**Item rules:**

- If data are not centre-based (for example a population survey), mark number_of_centres not_applicable and judge only setting and location.

#### T-6b

**Elements judged:**

- **eligibility_criteria**
- **continuous_variable_restrictions** (if eligibility involves a continuous variable such as age)

**Evidence a reviewer should look for:**

- A passage listing who was included and who was excluded, or stating that all consecutive eligible people were included together with the entry condition.

**Retrieval queries:**

- inclusion criteria exclusion criteria participants
- eligible participants aged
- patients were excluded if
- flow diagram of participants excluded

**Misinterpretations that mislead an LLM:**

- A flow diagram listing exclusion counts and reasons can serve as evidence, but only if the reasons are readable in the excerpts.
- The statement that all patients were included is not a criterion unless the entry condition is stated.
- Exclusions applied after data cleaning (for example missing data) are not eligibility criteria unless the paper presents them as such. Record the distinction.
- Age range given only in a results table of characteristics is not an eligibility restriction.

**Item rules:** none

#### T-8a

**Elements judged:**

- **outcome_definition**
- **how_outcome_assessed**
- **timing_or_time_horizon**
- standard_definition_cited
- rationale_for_outcome
- consistency_across_groups
- predictors_not_in_outcome

**Evidence a reviewer should look for:**

- A passage defining the outcome precisely enough to be reproduced.
- A passage stating how and when the outcome was determined.
- For prognostic models, a passage stating the prediction time horizon.

**Retrieval queries:**

- outcome definition primary outcome was defined as
- outcome ascertainment reference standard how outcome was assessed
- time horizon follow-up period for the outcome
- mortality within days of admission definition

**Misinterpretations that mislead an LLM:**

- Naming the outcome (for example mortality) is not defining it. Look for the definition, timing and method.
- A time horizon is required for prognostic models only. For diagnostic models the reference standard plays that role.
- Outcome labels in a results table do not show how the outcome was assessed.
- Do not infer consistency across groups from silence.

**Item rules:**

- Use the study profile to decide whether the model is diagnostic or prognostic. If uncertain, mark timing_or_time_horizon unclear and flag for the reviewer.

#### T-9b

**Elements judged:**

- **predictor_list_and_definitions**
- **units_and_categories**
- **how_measured**
- **when_measured**
- blinding_of_predictor_assessment (if predictor measurement involves interpretation)

**Evidence a reviewer should look for:**

- A passage or table that names every predictor with its definition.
- A passage or table giving units or categories.
- A passage stating how and when predictors were measured.

**Retrieval queries:**

- predictors candidate variables definitions units
- predictors were measured at admission
- table of predictor variables and categories
- features used as input to the model

**Misinterpretations that mislead an LLM:**

- A list of variable names alone does not define them, state units or say how they were measured.
- A table of baseline characteristics is not necessarily a predictor definition table. Check that the variables are the model inputs.
- A final model with many predictors may list them in supplementary material. If only that is available, use not_found_in_main_text and say so.
- Timing relative to intended use is required, not just a calendar timing.

**Item rules:** none

#### T-10

**Elements judged:**

- **how_size_was_determined**
- **justification_of_sufficiency**
- **separate_for_development_and_evaluation** (if study both develops and evaluates a model on separate data)

**Evidence a reviewer should look for:**

- A passage about sample size or sample size calculation.
- A passage justifying sufficiency, not merely stating the number analysed.

**Retrieval queries:**

- sample size calculation events per predictor
- sample size was determined by availability of data
- sufficient sample size to develop or evaluate the model
- minimum sample size criteria

**Misinterpretations that mislead an LLM:**

- Reporting that N participants were analysed is a result, not an explanation of how study size was arrived at.
- Using all available data is acceptable only if the paper also justifies sufficiency.
- A limitation sentence about small sample size acknowledges a problem but does not justify the size. Record it as partial at most.
- Do not judge whether the sample size was adequate. That is a PROBAST+AI question, not a TRIPOD+AI one.

**Item rules:**

- If the study has no separate evaluation dataset, mark separate_for_development_and_evaluation not_applicable.

#### T-11

**Elements judged:**

- **handling_method**
- extent_of_missingness
- **reasons_for_omitting_data** (if data were omitted because of missing values)
- **imputation_details** (if imputation was used)
- no_leakage_between_training_and_test (if imputation was used with data partitioning)

**Evidence a reviewer should look for:**

- A passage describing the missing-data approach.
- If participants were excluded for missing data, a passage giving the reason or rule.

**Retrieval queries:**

- missing data handled multiple imputation complete case analysis
- participants with missing values were excluded
- proportion of missing values per variable
- imputation was performed separately in training and test sets

**Misinterpretations that mislead an LLM:**

- A statement that there were no missing data is a valid report if it is explicit. Record as reported or author_stated_unavailable as appropriate.
- Missing data counts in a characteristics table do not describe how they were handled.
- Exclusions listed in a flow diagram for missing data count as reasons for omitting data.
- Do not judge whether the approach was appropriate. That is a PROBAST+AI question.

**Item rules:** none

#### T-12e

**Elements judged:**

- **discrimination_measure**
- **calibration_measure_or_plot**
- other_measures_clinical_utility
- **time_points_evaluated** (if model is prognostic)
- **model_comparison_methods** (if more than one model is evaluated)

**Evidence a reviewer should look for:**

- A Methods passage listing the performance measures.
- A passage naming how calibration was assessed.

**Retrieval queries:**

- model performance was assessed using discrimination and calibration
- c-statistic AUC calibration slope calibration plot decision curve analysis
- performance measures sensitivity specificity net benefit
- comparison of models performance criteria

**Misinterpretations that mislead an LLM:**

- This item concerns the Methods specification of measures. Results reporting of estimates belongs to item 23a.
- Accuracy, precision and recall alone do not cover discrimination and calibration as the guidance expects. Record what is named and mark calibration as missing if absent.
- Calibration is often presented only as a figure in Results. Count it as reported only if the text or caption identifies it.
- Whether calibration is expected as a minimum comes from the expanded guidance, not from the item wording. Show this in the rationale.

**Item rules:**

- Treat discrimination and calibration as required elements because the expanded guidance describes them as generally expected as a minimum (see unresolved question 1).

#### T-16

**Elements judged:**

- **setting_differences**
- **eligibility_differences**
- **outcome_differences**
- **predictor_differences**

**Evidence a reviewer should look for:**

- A passage that compares the development and evaluation datasets on each of the four domains, or that states they were the same.

**Retrieval queries:**

- differences between the development and external validation cohorts
- compared with the development cohort the validation cohort
- outcome and predictor definitions differed between datasets
- external evaluation setting eligibility criteria differences

**Misinterpretations that mislead an LLM:**

- A table showing baseline characteristics of both cohorts (item 20c) is related but does not by itself identify differences in setting, eligibility, outcome definition or predictor definitions.
- Differences in case-mix or prevalence are not the same as differences in definitions. Record what is stated.
- Do not infer differences yourself by comparing two descriptions. Only mark reported if the paper itself states them or states there are none.
- A single-dataset study has no evaluation dataset to compare against.

**Item rules:**

- If the study has no separate evaluation dataset (for example development with only internal validation), mark the item not_applicable and say so in the rationale. This is a ModelAudit operational rule (see unresolved question 3).

#### T-18e

**Elements judged:**

- **availability_statement**
- **location_or_access_route** (if data are stated to be available)
- **conditions_or_reasons**
- data_dictionary

**Evidence a reviewer should look for:**

- A data availability statement in the main text, usually near the end of the paper.

**Retrieval queries:**

- data availability statement
- data are available from repository or upon request
- data sharing restrictions and access conditions
- dataset publicly available DOI URL

**Misinterpretations that mislead an LLM:**

- Data available upon reasonable request, without conditions, is the platitude the guidance warns against. Mark partially_reported and explain.
- Availability of the original public dataset (for example a public survey) can count if the paper says how to access it.
- Code availability is item 18f, not this item.
- Data availability statements are often outside the main body. If none is found, use not_found_in_main_text.

**Item rules:**

- Platitude-only statements are partially_reported, never reported.

#### T-18f

**Elements judged:**

- **availability_statement**
- **location_or_access_route** (if code is stated to be available)
- **conditions_licence_or_reasons**
- software_and_versions

**Evidence a reviewer should look for:**

- A code availability statement or a repository link with an indication that it holds the analysis code.

**Retrieval queries:**

- code availability statement
- analysis code is available at GitHub repository
- software and packages used with version numbers
- code is available from the authors on request

**Misinterpretations that mislead an LLM:**

- A link to a deployed web tool or model object is not necessarily the analytical code. Check what the link contains, and see item 22 for model availability.
- A statement that code is available from the authors without conditions is partial.
- Listing software without versions does not by itself satisfy the availability element.
- Data availability is item 18e, not this item.

**Item rules:**

- Statements giving only that code is available on request, with no location or conditions, are partially_reported.

#### T-23a

**Elements judged:**

- **estimates_reported**
- **confidence_intervals**
- **data_used_for_each_estimate**
- subgroup_performance
- **time_points** (if model is prognostic)

**Evidence a reviewer should look for:**

- A Results passage or table with numerical estimates and intervals.
- A statement of which data produced each estimate.

**Retrieval queries:**

- model performance c-statistic AUC with 95% confidence interval
- calibration slope and intercept results
- performance in subgroups by sex age or region
- table of discrimination and calibration in development and validation cohorts

**Misinterpretations that mislead an LLM:**

- Estimates without intervals are partial. Do not infer intervals from standard errors that are not given.
- Results in a figure whose numbers are not in the excerpts cannot be verified. Use unclear and flag for the reviewer.
- Apparent performance in the development data and internal or external evaluation estimates are different. Record which are shown.
- Subgroup results are in the item wording but are non-required here by decision (see unresolved question 1).

**Item rules:**

- If estimates are reported only for development data when an evaluation was done, mark partially_reported.

### 2.3 Illustrative examples

| ID | Sufficient | Insufficient |
|---|---|---|
| T-3b | The model is intended for adults attending primary care clinics in Nigeria, to help nurses decide on referral for confirmatory blood pressure measurement. | We developed a model to improve hypertension care. |
| T-5a | We used a nationally representative household survey collected for other purposes. We considered it suitable because sampling covered all regions of the target country. | Data came from a national survey. |
| T-5b | Participants were enrolled between January 2015 and December 2017, with follow-up to 31 December 2018. | Data were obtained from a hospital database. |
| T-6a | Participants attended outpatient clinics at four tertiary hospitals in Lagos, Nigeria. | This was a multicentre study. |
| T-6b | Adults aged 18 to 80 years with a first hospital admission were eligible. Patients on chronic dialysis were excluded. | Eligible patients were included in the study. |
| T-8a | The outcome was all-cause in-hospital death during the index admission, ascertained from hospital records, with no censoring. | The outcome was mortality. |
| T-9b | Systolic blood pressure (mmHg) was measured with a validated oscillometric device at triage, before any treatment. Smoking was coded never, former or current. | Clinical and laboratory variables were used as predictors. |
| T-10 | No formal calculation was done. All 3,204 eligible patients were used. We judged this sufficient because the number of outcome events exceeded the minimum implied by the criteria of Riley and colleagues for 12 candidate predictors. | The sample size was adequate. |
| T-11 | Predictors with more than 30 percent missing values were dropped. Remaining missing values (2 to 11 percent) were imputed by multiple imputation with chained equations (20 imputations), fitted in the training data only. | Missing data were handled appropriately. |
| T-12e | Performance was assessed by the c-statistic (discrimination) and by calibration slope, calibration-in-the-large and smoothed calibration plots. Clinical utility was assessed by decision curve analysis. | Performance was assessed using accuracy and F1 score. |
| T-16 | Compared with the development cohort, the evaluation cohort was recruited in primary care rather than hospitals, excluded pregnant women, and defined hypertension from a single clinic reading. Predictors were measured identically. | The external cohort differed in some respects. |
| T-18e | The data are held in a public repository at the stated DOI. Access requires registration and acceptance of a data use agreement. A data dictionary is included. | Data available upon reasonable request. |
| T-18f | All analysis code, with Python 3.10 and package versions, is available at the stated repository release under an MIT licence. | Code is available from the authors. |
| T-23a | In the external cohort the c-statistic was 0.78 (95% CI 0.74 to 0.82) overall, 0.80 (0.75 to 0.85) in women and 0.75 (0.69 to 0.81) in men. | The AUC was 0.78. |

## 3. The machine-readable framework

The JSON file is the executable representation used by the backend. It contains the selected item definitions, element-level requirements, retrieval guidance, item-specific rules, judgement categories and prompt instructions.

The extraction checks recorded here found that the file parses as valid JSON, the 14 selected items use a consistent structure, element keys are unique within each item, and the item categories are represented in the top-level judgement scheme.

Delivered as `backend/framework/tripod_ai_subset.json`. It parses with the standard library `json` module, has no comments, and I checked that all 14 items share an identical key set, that element keys carry a required flag, and that every item's judgement_categories are defined in the top-level judgement_scheme.

## 4. Implementation design

The framework keeps language-model assistance separate from decisions that can be made deterministically. This improves traceability: a reviewer can inspect the element-level finding, the cited source passage, the verification result and the rule used to derive the item category.

### 4.1 Core design principle

The JSON framework is the single source of truth for checklist content and item-specific assessment instructions. This avoids duplicating or gradually drifting from published item wording in application code. The language model proposes element-level findings and supporting quotations; deterministic code verifies whether the quotations occur in the source and derives the item category. A human reviewer remains responsible for accepting, amending or rejecting the proposed assessment.

### 4.2 Assessment data contract

Proposed Pydantic models for `schemas.py`. Names are suggestions, shapes are the point.

```python
class FrameworkElement(BaseModel):
    key: str
    description: str
    required: bool
    required_when: str | None = None


class FrameworkItem(BaseModel):
    id: str
    section: str
    official_item_text: str
    applies_to: list[Literal["development", "evaluation"]]
    assessment_prompt: str
    elements: list[FrameworkElement]
    evidence_requirements: list[str]
    retrieval_queries: list[str]
    common_misinterpretations: list[str]
    item_rules: list[str]
    judgement_categories: list[str]


# --- request ---
class ItemAssessmentRequest(BaseModel):
    document_id: str
    item_id: str
    study_type: Literal["development", "evaluation", "both"]   # confirmed by reviewer
    mode: Literal["retrieval", "full_context"] = "retrieval"
    top_k: int = 6


class EvidenceChunk(BaseModel):          # what the model sees
    chunk_id: str
    page: int
    text: str
    rank: int
    score: float
    retrieved_by: list[str]              # which retrieval queries surfaced it


# --- what the LLM must return (validated) ---
class EvidenceRef(BaseModel):
    chunk_id: str
    page: int
    quote: str                           # verbatim, max 300 characters


class ElementFinding(BaseModel):
    element_key: str
    status: Literal["reported", "partially_reported", "author_stated_unavailable",
                    "not_found_in_main_text", "unclear", "not_applicable"]
    evidence: list[EvidenceRef]
    note: str                            # one sentence


class LLMItemJudgement(BaseModel):
    item_id: str
    element_findings: list[ElementFinding]
    proposed_category: str
    rationale: str
    flags: list[Literal["possible_supplement", "conflicting_evidence",
                        "retrieval_may_be_incomplete", "study_type_uncertain"]]


# --- what the system stores ---
class QuoteVerification(BaseModel):
    element_key: str
    chunk_id: str
    status: Literal["exact", "fuzzy", "not_found"]
    score: float
    page_ok: bool
    support_check: Literal["pending", "supports", "does_not_support"] = "pending"


class ItemAssessment(BaseModel):
    assessment_id: str
    document_id: str
    item_id: str
    framework_hash: str                  # sha256 of the JSON file
    prompt_hash: str
    element_findings: list[ElementFinding]   # after verification downgrades
    derived_category: str
    proposed_category: str
    category_mismatch: bool
    verification: list[QuoteVerification]
    retrieval: dict                      # queries, chunk_ids, mode, top_k
    llm: dict                            # model id, temperature, tokens, cached
    flags: list[str]


class ReviewDecision(BaseModel):
    assessment_id: str
    decision: Literal["accepted", "amended", "rejected"]
    final_category: str
    element_overrides: dict[str, str] = {}
    note: str = ""
    reviewer: str
```

### 4.3 Deriving item-level judgements

Take the required, applicable elements after verification downgrades. If an element's status is reported or partially_reported but none of its evidence verified, set it to unclear and add the flag evidence_unverified. Then:

1. No required applicable elements: not_applicable.
2. All required elements reported or author_stated_unavailable: reported if at least one is reported, otherwise author_stated_unavailable.
3. All required elements not_found_in_main_text: not_found_in_main_text.
4. Some required element unclear and none reported or partial: unclear.
5. Otherwise: partially_reported.

If the model's proposed_category differs from the derived one, set category_mismatch and show it to the reviewer. Conditional elements (required_when) are evaluated by the model as not_applicable with a note, and the reviewer can override. If you want that machine-checked later, make required_when a small structured field.

### 4.4 How the components fit together

- `framework.py` (new, about 40 lines): load the JSON, validate against `FrameworkItem`, compute the file hash, expose `get_item(id)` and `list_items(study_type)`. It is small enough that adding it does not change the architecture.
- `schemas.py`: add the models above next to the existing retrieval schemas.
- `retrieval.py`: add one function, `retrieve_for_item(index, item, top_k)`. It runs each of the item's `retrieval_queries` through your existing hybrid retriever, merges by chunk_id, keeps the best rank, and records which query found each chunk. Do not touch the ranking code.
- `llm.py`: one function, `complete_json(system, user, response_model)` with temperature 0, Pydantic validation, one retry on validation failure, token logging, and a cache keyed on (document hash, item id, framework hash, prompt hash, model).
- `judge.py`: `assess_item(request)` loads the item, retrieves, renders `judge_prompt_template` with the item, global rules and item rules, calls the LLM, validates, calls verify, derives the category, and returns an `ItemAssessment`.
- `verify.py`: normalise whitespace, line-break hyphenation, ligatures and curly quotes on both quote and chunk. Try an exact match in the cited chunk, then fuzzy matching in that chunk, then anywhere in the document, and check the page. Verification only proves the quotation exists. Leave `support_check` as pending for human review and for the evaluation sample.
- `audit.py`: append-only SQLite table of events (assessment_created, verification_completed, review_decision) storing full snapshots, framework_hash, prompt_hash, actor and timestamp. Never update rows.
- `main.py`: when you get there, three endpoints are enough: run an item assessment, list assessments for a document, post a review decision.

### 4.5 Implementation sequence

1. Models in `schemas.py`, `framework.py`, and a loader test: 14 items, unique IDs, unique element keys per item, categories subset of the scheme.
2. The pure derivation function with table-driven tests. No LLM needed.
3. `verify.py` with tests for ligatures, hyphenation and fuzzy matches.
4. `llm.py`, then `judge.py` with a mocked LLM contract test.
5. `audit.py`.
6. One real run on the Chen et al. 2020 paper, starting with T-5b and

> **[Note: step 6 is cut off mid-sentence in the source text and could not be completed without inventing content.]**

## 5. Operational decisions and limitations

Some choices are necessary to turn checklist guidance into a functioning assessment workflow. They should remain visible rather than being mistaken for official TRIPOD+AI rules. This section records the decisions adopted for the MVP and the areas where the implementation uses an explicit operational interpretation.

1. **Which elements are required.** For the MVP, the rationale and group-consistency elements in item 8a are optional; calibration is required in item 12e because the expanded guidance describes discrimination and calibration as generally expected minimum measures; and subgroup performance is optional in item 23a. These are explicit operational choices. A stricter required-element policy would cause more items to be classified as partially reported.
2. **Date granularity for 5b.** The MVP accepts year-level date ranges. This is a deliberate granularity choice; month-level dates are not required by the current implementation.
3. **Studies with no separate evaluation dataset.** For a study without a separate evaluation dataset, the MVP treats item 16 and the elements that specifically require separate development and evaluation data in items 5a, 5b and 10 as not applicable. This is a ModelAudit operational rule. The source marks these checklist items D;E, so the rule must not be presented as an exemption stated by TRIPOD+AI.
4. **Deterministic category derivation.** The recommended approach is to derive the category in code as in C3, with the model's proposal as a cross-check. If you prefer the model to choose freely, the audit trail gets weaker.
5. **Examples in prompts.** The recommended approach is to keep the synthetic examples out of prompts at first and use them for tests and reviewer help, to avoid anchoring. Say if you want them in.

---

## 6. Intended use and interpretation

ModelAudit uses this subset to support a structured review of reporting completeness. It does not replace the full TRIPOD+AI checklist, determine whether a prediction model is methodologically sound, or establish that a model is clinically safe or ready for implementation.

A finding that an item is reported means that the relevant reporting element was identified and its cited quotation was verified against the source text. It does not, by itself, establish that the reported method was appropriate or that the evidence semantically supports every aspect of the finding. Those judgements remain subject to human review.

The framework should therefore be understood as an auditable decision-support component: it helps reviewers locate and organise relevant reporting evidence, makes its operational rules explicit, and preserves the distinction between what the paper says and what the assessment system concludes.
