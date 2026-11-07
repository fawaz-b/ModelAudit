import { useState } from 'react'
import './App.css'

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000').replace(/\/$/, '')

type JsonObject = Record<string, any>
type Framework = 'tripod' | 'probast'

const tripodFields = [
  ['has_separate_evaluation_dataset', 'Was a separate evaluation dataset used?'],
  ['synthetic_data_used', 'Was synthetic data used?'],
  ['multiple_or_identifiable_centres', 'Were multiple or identifiable centers involved?'],
  ['eligibility_uses_continuous_restriction', 'Were eligibility criteria based on continuous restrictions?'],
  ['predictor_assessment_requires_interpretation', 'Did predictor assessment require interpretation?'],
  ['data_omitted_due_to_missingness', 'Was data omitted due to missingness?'],
  ['imputation_used', 'Was imputation used?'],
  ['imputation_with_data_partitioning', 'Was imputation performed with data partitioning?'],
  ['multiple_models_evaluated', 'Were multiple models evaluated?'],
  ['data_stated_available', 'Was data availability stated?'],
  ['code_stated_available', 'Was code availability stated?'],
  ['subgroup_performance_evaluated_or_reported', 'Was subgroup performance evaluated or reported?'],
] as const

const picotsFields = [
  ['population', 'Population'],
  ['index_model', 'Index model'],
  ['comparator_model', 'Comparator model'],
  ['outcome', 'Outcome'],
  ['timing', 'Timing'],
  ['setting', 'Setting'],
  ['intended_use', 'Intended use'],
] as const

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Not supplied'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value).replaceAll('_', ' ')
}

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [document, setDocument] = useState<JsonObject | null>(null)
  const [selected, setSelected] = useState<Framework[]>(['tripod', 'probast'])
  const [activeTab, setActiveTab] = useState<Framework>('tripod')
  const [tripodContext, setTripodContext] = useState<JsonObject>({})
  const [probastContext, setProbastContext] = useState<JsonObject>({
    study_type: 'unclear',
    evaluation_components: ['unspecified'],
    validation_method: 'unclear',
    has_training_test_split: null,
    evaluation_dataset_independent: null,
    picots: {},
  })
  const [modelIdentifier, setModelIdentifier] = useState('')
  const [uploading, setUploading] = useState(false)
  const [running, setRunning] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [results, setResults] = useState<Partial<Record<Framework, JsonObject>>>({})
  const [runErrors, setRunErrors] = useState<Partial<Record<Framework, string>>>({})

  const uploaded = Boolean(document?.document_id)

  async function apiRequest(path: string, options: RequestInit = {}) {
    const response = await fetch(`${API_BASE}${path}`, options)
    const data = await response.json().catch(() => ({}))

    if (!response.ok) {
      throw new Error(data.detail || `Request failed (${response.status})`)
    }

    return data
  }

  async function uploadDocument() {
    if (!file) {
      setError('Choose a PDF before uploading.')
      return
    }

    setUploading(true)
    setError('')
    setMessage('')
    setResults({})
    setRunErrors({})

    const body = new FormData()
    body.append('file', file)

    try {
      const data = await apiRequest('/documents/upload', {
        method: 'POST',
        body,
      })

      setDocument(data)
      setMessage('Your paper has been uploaded and processed.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setUploading(false)
    }
  }

  async function runAssessments() {
    if (!document?.document_id) {
      setError('Upload a paper before starting an assessment.')
      return
    }

    if (selected.length === 0) {
      setError('Select at least one assessment framework.')
      return
    }

    setRunning(true)
    setError('')
    setMessage('Assessment running. This may take several minutes.')
    setRunErrors({})

    const nextResults: Partial<Record<Framework, JsonObject>> = {}
    const nextErrors: Partial<Record<Framework, string>> = {}

    for (const framework of selected) {
      try {
        if (framework === 'tripod') {
          const data = await apiRequest(
            `/documents/${document.document_id}/assess`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(tripodContext),
            },
          )
          nextResults.tripod = data
        }

        if (framework === 'probast') {
          const data = await apiRequest(
            `/documents/${document.document_id}/assess/probast`,
            {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                document_id: document.document_id,
                context: probastContext,
                model_identifier: modelIdentifier || null,
              }),
            },
          )
          nextResults.probast = data
        }

        setResults({ ...nextResults })
      } catch (err) {
        nextErrors[framework] = err instanceof Error
          ? err.message
          : 'Assessment failed.'
        setRunErrors({ ...nextErrors })
      }
    }

    setResults(nextResults)
    setRunErrors(nextErrors)
    setRunning(false)

    if (Object.keys(nextResults).length > 0) {
      setMessage('Assessment processing finished. Review the findings below.')
    } else {
      setMessage('')
    }
  }

  function toggleFramework(framework: Framework) {
    setSelected(current =>
      current.includes(framework)
        ? current.filter(item => item !== framework)
        : [...current, framework],
    )
  }

  function updateProbast(key: string, value: unknown) {
    setProbastContext(current => ({ ...current, [key]: value }))
  }

  function renderFindings(result: JsonObject, framework: Framework) {
    const findings = framework === 'tripod'
      ? result.items
      : result.findings

    if (!Array.isArray(findings) || findings.length === 0) {
      return <p className="muted">No item-level findings were returned.</p>
    }

    return (
      <div className="findings-list">
        {findings.map((finding: JsonObject, index: number) => {
          const id = finding.item_id || finding.question_id || `Finding ${index + 1}`
          const elements = Array.isArray(finding.element_findings)
            ? finding.element_findings
            : null

          return (
            <article className="finding-card" key={`${id}-${index}`}>
              <div className="finding-heading">
                <strong>{id}</strong>
                <span className="status">{displayValue(finding.category || finding.response || finding.assessment_state)}</span>
              </div>

              {finding.explanation && <p>{finding.explanation}</p>}
              {finding.reviewer_comment && (
                <p className="muted">Reviewer: {finding.reviewer_comment}</p>
              )}

              {elements && elements.map((element: JsonObject, elementIndex: number) => (
                <div className="element-row" key={element.element_key || elementIndex}>
                  <div className="finding-heading">
                    <strong>{element.element_key}</strong>
                    <span className="status">{displayValue(element.status)}</span>
                  </div>
                  <p>{element.explanation}</p>
                  <Evidence evidence={element.evidence} verified={element.evidence_verified} />
                </div>
              ))}

              {!elements && (
                <Evidence evidence={finding.evidence} verified={finding.evidence_verified} />
              )}

              {finding.flags?.length > 0 && (
                <p className="flag-text">Flags: {finding.flags.join('; ')}</p>
              )}
            </article>
          )
        })}
      </div>
    )
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#">
          <span className="brand-mark">M</span>
          <span>ModelAudit</span>
        </a>
        <span className="topbar-label">Clinical prediction model appraisal</span>
        <span className="environment-tag">Research preview</span>
      </header>

      <main className="main-content">
        <section className="page-intro">
          <div className="eyebrow">EVIDENCE-LINKED APPRAISAL WORKSPACE</div>
          <h1>Evaluate clinical prediction model research.</h1>
          <p>
            Assess reporting transparency with TRIPOD+AI and selected
            risk-of-bias questions with PROBAST+AI.
          </p>
        </section>

        <section className="notice">
          <strong>Research-use tool.</strong>
          <span>
            ModelAudit supports structured human review. Its outputs are not
            validated clinical judgements and should not replace expert appraisal.
          </span>
        </section>

        <section className="workspace-grid">
          <div className="primary-column">
            <section className="panel">
              <div className="section-heading">
                <div>
                  <span className="step-number">01</span>
                  <h2>Upload your paper</h2>
                </div>
                <span className="step-caption">PDF · 15 MB max · 40 pages max</span>
              </div>

              <label className="upload-zone">
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={event => {
                    setFile(event.target.files?.[0] || null)
                    setDocument(null)
                    setResults({})
                    setError('')
                    setMessage('')
                  }}
                />
                <span className="upload-icon">↑</span>
                <strong>{file ? file.name : 'Choose a research paper'}</strong>
                <span>{file ? `${(file.size / 1024 / 1024).toFixed(2)} MB` : 'Select a PDF from your device'}</span>
              </label>

              <button className="button button-primary" onClick={uploadDocument} disabled={!file || uploading}>
                {uploading ? 'Uploading paper…' : uploaded ? 'Upload another paper' : 'Upload and process PDF'}
              </button>

              {document && (
                <div className="document-summary">
                  <span className="success-dot" />
                  <div>
                    <strong>{document.filename}</strong>
                    <p>{document.page_count} pages · {document.chunk_count} text chunks</p>
                  </div>
                </div>
              )}
            </section>

            <section className="panel">
              <div className="section-heading">
                <div>
                  <span className="step-number">02</span>
                  <h2>Select assessments</h2>
                </div>
              </div>

              <div className="framework-options">
                <label className={`framework-option ${selected.includes('tripod') ? 'selected' : ''}`}>
                  <input
                    type="checkbox"
                    checked={selected.includes('tripod')}
                    onChange={() => toggleFramework('tripod')}
                  />
                  <span className="framework-code">T</span>
                  <span className="framework-copy">
                    <strong>TRIPOD+AI</strong>
                    <small>Reporting transparency checklist</small>
                  </span>
                  <span className="check-mark">{selected.includes('tripod') ? '✓' : ''}</span>
                </label>

                <label className={`framework-option ${selected.includes('probast') ? 'selected' : ''}`}>
                  <input
                    type="checkbox"
                    checked={selected.includes('probast')}
                    onChange={() => toggleFramework('probast')}
                  />
                  <span className="framework-code probast-code">P</span>
                  <span className="framework-copy">
                    <strong>PROBAST+AI</strong>
                    <small>Selected evaluation-branch questions</small>
                  </span>
                  <span className="check-mark">{selected.includes('probast') ? '✓' : ''}</span>
                </label>
              </div>
            </section>

            {selected.includes('tripod') && (
              <section className="panel">
                <div className="section-heading">
                  <div>
                    <span className="step-number">03A</span>
                    <h2>TRIPOD+AI study context</h2>
                  </div>
                </div>
                <p className="helper-text">
                  Supply known study characteristics to help resolve conditional checklist items.
                  Leave uncertain fields unanswered.
                </p>

                <label className="field-label">
                  Study type
                  <input
                    value={tripodContext.study_type || ''}
                    onChange={event => setTripodContext(current => ({
                      ...current,
                      study_type: event.target.value || null,
                    }))}
                    placeholder="e.g. Prognostic model development"
                  />
                </label>

                <div className="context-grid">
                  {tripodFields.map(([key, label]) => (
                    <label className="field-label" key={key}>
                      {label}
                      <select
                        value={tripodContext[key] === true ? 'true' : tripodContext[key] === false ? 'false' : ''}
                        onChange={event => setTripodContext(current => ({
                          ...current,
                          [key]: event.target.value === '' ? null : event.target.value === 'true',
                        }))}
                      >
                        <option value="">Not sure / not supplied</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    </label>
                  ))}
                </div>
              </section>
            )}

            {selected.includes('probast') && (
              <section className="panel">
                <div className="section-heading">
                  <div>
                    <span className="step-number">03B</span>
                    <h2>PROBAST+AI study context</h2>
                  </div>
                </div>
                <p className="helper-text">
                  These fields describe the prediction model and its evaluation.
                  Use “unclear” or leave PICOTS fields blank when information is unavailable.
                </p>

                <div className="context-grid">
                  <label className="field-label">
                    Study type
                    <select
                      value={probastContext.study_type}
                      onChange={event => updateProbast('study_type', event.target.value)}
                    >
                      <option value="unclear">Unclear</option>
                      <option value="development">Development</option>
                      <option value="evaluation">Evaluation</option>
                      <option value="both">Development and evaluation</option>
                    </select>
                  </label>

                  <label className="field-label">
                    Validation method
                    <select
                      value={probastContext.validation_method}
                      onChange={event => updateProbast('validation_method', event.target.value)}
                    >
                      <option value="unclear">Unclear</option>
                      <option value="training_test_split">Training/test split</option>
                      <option value="bootstrap">Bootstrap</option>
                      <option value="cross_validation">Cross-validation</option>
                      <option value="other_resampling">Other resampling</option>
                      <option value="none">None</option>
                    </select>
                  </label>

                  <label className="field-label">
                    Training/test split used?
                    <select
                      value={probastContext.has_training_test_split === null ? '' : String(probastContext.has_training_test_split)}
                      onChange={event => updateProbast('has_training_test_split', event.target.value === '' ? null : event.target.value === 'true')}
                    >
                      <option value="">Not sure</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  </label>

                  <label className="field-label">
                    Evaluation dataset independent?
                    <select
                      value={probastContext.evaluation_dataset_independent === null ? '' : String(probastContext.evaluation_dataset_independent)}
                      onChange={event => updateProbast('evaluation_dataset_independent', event.target.value === '' ? null : event.target.value === 'true')}
                    >
                      <option value="">Not sure</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  </label>
                </div>

                <label className="field-label">
                  Evaluation component
                  <select
                    value={probastContext.evaluation_components[0]}
                    onChange={event => updateProbast('evaluation_components', [event.target.value])}
                  >
                    <option value="unspecified">Unspecified</option>
                    <option value="apparent">Apparent</option>
                    <option value="internal">Internal</option>
                    <option value="external">External</option>
                  </select>
                </label>

                <label className="field-label">
                  Model identifier (optional)
                  <input
                    value={modelIdentifier}
                    onChange={event => setModelIdentifier(event.target.value)}
                    placeholder="Name or description of the prediction model"
                  />
                </label>

                <h3 className="subsection-title">PICOTS context</h3>
                <div className="context-grid">
                  {picotsFields.map(([key, label]) => (
                    <label className="field-label" key={key}>
                      {label}
                      <input
                        value={probastContext.picots[key] || ''}
                        onChange={event => setProbastContext(current => ({
                          ...current,
                          picots: {
                            ...current.picots,
                            [key]: event.target.value || null,
                          },
                        }))}
                        placeholder={`${label} (optional)`}
                      />
                    </label>
                  ))}
                </div>
              </section>
            )}

            <section className="run-panel">
              <div>
                <span className="step-number">04</span>
                <h2>Run assessment</h2>
                <p>Selected frameworks will be processed against the uploaded paper.</p>
              </div>
              <button
                className="button button-primary run-button"
                onClick={runAssessments}
                disabled={!uploaded || selected.length === 0 || running}
              >
                {running ? 'Running assessment…' : 'Start assessment'}
              </button>
            </section>

            {(message || error) && (
              <div className={error ? 'alert alert-error' : 'alert alert-success'}>
                {error || message}
              </div>
            )}
          </div>

          <aside className="side-column">
            <section className="panel side-panel">
              <span className="eyebrow">WORKSPACE STATUS</span>
              <h2>Your assessment</h2>
              <div className="status-line">
                <span className={uploaded ? 'status-indicator ready' : 'status-indicator'} />
                <span>{uploaded ? 'Paper uploaded' : 'Awaiting paper upload'}</span>
              </div>
              <div className="status-line">
                <span className={selected.length ? 'status-indicator ready' : 'status-indicator'} />
                <span>{selected.length} framework(s) selected</span>
              </div>
              <div className="status-line">
                <span className={Object.keys(results).length ? 'status-indicator ready' : 'status-indicator'} />
                <span>{Object.keys(results).length} assessment(s) returned</span>
              </div>
              <div className="side-divider" />
              <p className="muted small">
                Assessments run independently. A successful result from one framework
                does not imply that the other has completed.
              </p>
            </section>

            <section className="panel side-panel">
              <span className="eyebrow">IMPORTANT LIMITATIONS</span>
              <h2>Human review remains essential.</h2>
              <ul className="limitations-list">
                <li>TRIPOD+AI evaluates reporting, not methodological quality.</li>
                <li>PROBAST+AI currently covers a selected question-level subset.</li>
                <li>Evidence location verification does not establish semantic support.</li>
                <li>Missing evidence in the main text does not prove that information is absent elsewhere.</li>
              </ul>
            </section>
          </aside>
        </section>

        {Object.keys(results).length > 0 && (
          <section className="results-section">
            <div className="results-header">
              <div>
                <span className="eyebrow">ASSESSMENT OUTPUT</span>
                <h2>Review findings</h2>
              </div>
              <div className="tab-list">
                {(['tripod', 'probast'] as Framework[]).map(framework => (
                  <button
                    key={framework}
                    className={`tab-button ${activeTab === framework ? 'active' : ''}`}
                    onClick={() => setActiveTab(framework)}
                    disabled={!results[framework]}
                  >
                    {framework === 'tripod' ? 'TRIPOD+AI' : 'PROBAST+AI'}
                  </button>
                ))}
              </div>
            </div>

            {runErrors[activeTab] && (
              <div className="alert alert-error">{runErrors[activeTab]}</div>
            )}

            {results[activeTab] && (
              <div className="panel results-panel">
                <div className="result-summary">
                  <div>
                    <span className="eyebrow">FRAMEWORK</span>
                    <h3>{results[activeTab]?.framework_name || results[activeTab]?.framework_id || (activeTab === 'tripod' ? 'TRIPOD+AI' : 'PROBAST+AI')}</h3>
                  </div>
                  <span className="status">{displayValue(results[activeTab]?.assessment_status)}</span>
                </div>

                {activeTab === 'probast' && (
                  <div className="coverage-summary">
                    <strong>PROBAST+AI evaluation subset</strong>
                    <p>
                      Question-level findings only. Domain-level risk-of-bias
                      judgements and overall judgements are not generated by this MVP.
                    </p>
                    {Array.isArray(results.probast?.domains) && (
                      <div className="domain-grid">
                        {results.probast.domains.map((domain: JsonObject) => (
                          <div className="domain-card" key={domain.domain_id}>
                            <strong>{domain.domain_id}</strong>
                            <span>{domain.included_questions?.length || 0} included questions</span>
                            <small>Risk of bias: not assessed</small>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {renderFindings(results[activeTab]!, activeTab)}

                {Array.isArray(results[activeTab]?.limitations) && (
                  <div className="limitations-output">
                    <h3>Assessment limitations</h3>
                    <ul>
                      {results[activeTab]!.limitations.map((item: string, index: number) => (
                        <li key={index}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </section>
        )}
      </main>

      <footer className="footer">
        <span>ModelAudit</span>
        <span>Research support · Human review required</span>
      </footer>
    </div>
  )
}

function Evidence({ evidence, verified }: { evidence?: JsonObject[]; verified?: boolean }) {
  if (!Array.isArray(evidence) || evidence.length === 0) {
    return <p className="muted small">No evidence quotation returned.</p>
  }

  return (
    <div className="evidence-block">
      <div className="evidence-label">
        Evidence references
        <span className={verified ? 'verified' : 'unverified'}>
          {verified ? 'Location verified' : 'Not verified'}
        </span>
      </div>
      {evidence.map((item, index) => (
        <blockquote key={index}>
          “{item.quote}”
          <cite>Page {item.page} · {item.chunk_id}</cite>
        </blockquote>
      ))}
      <p className="muted small">
        Location verification checks whether a quotation can be located in the source.
        It does not establish that the quotation supports the finding.
      </p>
    </div>
  )
}

export default App
