Use the EXISTING DAISY frontend prototype in this project as the visual and UX foundation.

DO NOT rebuild the landing page from scratch.
DO NOT replace the current design.
DO NOT create a generic dashboard.
DO NOT change the existing visual identity.

Instead, EXTEND the existing prototype into the actual functional DAISY application by connecting the frontend experience to the existing backend workflow.

The current prototype is already the approved base design. Preserve its:

- black / near-black background
- warm gold/amber lighting
- cream typography
- gold accents
- Bricolage Grotesque display typography
- Instrument Sans UI typography
- IBM Plex Mono technical typography
- glassmorphism
- floating glass cards
- rounded pill buttons
- large editorial typography
- subtle borders
- atmospheric gradients
- gold glow effects
- animations
- spacing and visual hierarchy
- D.A.I.S.Y branding
- overall premium cinematic AI-product aesthetic

The result should look like the SAME product evolving from a landing page into a live ML workspace.

==================================================
CORE REQUIREMENT
==================================================

The frontend must be DYNAMIC and BACKEND-DRIVEN.

The backend is already implemented.

Do not create mock data.
Do not create fake API responses.
Do not simulate backend operations with setTimeout.
Do not hardcode dataset information.
Do not hardcode model results.
Do not hardcode metrics.
Do not hardcode agent output.
Do not hardcode progress percentages.

EVERY runtime value must come from actual backend responses/application state.

If backend data does not exist yet, show an appropriate empty/loading state instead of inventing data.

==================================================
START A RUN
==================================================

The existing landing page has the "Start a run →" CTA.

Make this CTA functional.

When the user clicks it, transition from the existing landing experience into the DAISY ML workspace.

Do NOT navigate to an unrelated dashboard.

The workspace should feel like the existing landing page has transformed into the live DAISY environment.

==================================================
ACTUAL DAISY WORKFLOW
==================================================

The real workflow is:

DATASET UPLOAD
↓
DATA CLEANING
↓
EDA
↓
FEATURE ENGINEERING
↓
TARGET COLUMN SELECTION
↓
MODEL SELECTION
↓
MODEL TRAINING
↓
BEST MODEL / RESULTS

The frontend must represent this exact workflow.

The 3D/pipeline visual already present in the project should become state-aware.

Pipeline stages should visually change according to the real backend state:

NOT STARTED
AVAILABLE
RUNNING
COMPLETED
ERROR
WAITING FOR USER INPUT

Do not make all stages active at the same time.

==================================================
DATASET UPLOAD
==================================================

After "Start a run", provide a dataset upload experience.

Allow CSV upload.

Connect it to the real backend upload functionality.

After successful upload, use the backend response to populate the interface.

Display only information actually returned by the backend.

For example, if returned:

- filename
- dataset ID
- row count
- column count
- schema
- data types

display those values dynamically.

Never create example values.

The existing floating glass-card aesthetic should be reused for dataset information.

==================================================
DATA CLEANING
==================================================

After upload, allow the user to trigger the real Data Cleaning Agent.

When running:

- DATA stage becomes active
- show appropriate animation
- show agent running state
- disable duplicate execution

After completion:

Display the REAL cleaning results returned by the backend.

Use reusable dynamic action components.

If the backend returns cleaning actions, render them.

If it returns affected columns, render them.

If it returns before/after information, render it.

Do not invent actions or numbers.

==================================================
EDA
==================================================

After cleaning, allow the user to run the EDA Agent.

Use the actual backend response.

Create a beautiful DAISY-style analysis panel for the returned EDA output.

The panel can display:

- AI analysis
- observations
- insights
- summaries
- other returned information

But only if those values actually exist in the response.

Do not fabricate EDA findings.

==================================================
FEATURE ENGINEERING
==================================================

After EDA, allow the user to run Feature Engineering.

Use the real backend response.

Clearly distinguish:

AI-generated feature engineering actions

from

deterministic fallback transformations

when that distinction exists in the response.

Display actual transformations and actual resulting schema information.

Do not invent column names or transformation counts.

==================================================
TARGET COLUMN
==================================================

After feature engineering, reveal a target-column selection interface.

Populate the selector dynamically using the actual engineered dataset columns.

Do NOT hardcode:

target
price
churn
sales
etc.

The available columns must come from backend/application state.

The user selects the column they want to predict.

Only after target selection should Model Selection become available.

==================================================
MODEL SELECTION
==================================================

After target selection, trigger the real Model Selection Agent.

Display the actual backend result.

If the backend determines:

- problem type
- candidate models
- accepted models
- rejected models
- rankings
- reasoning

display those values dynamically.

Do not hardcode model names.

Do not hardcode "classification" or "regression".

Do not invent reasoning.

Use reusable model recommendation cards.

==================================================
MODEL TRAINING
==================================================

After model selection, allow the user to train the accepted models.

Training must call the real backend.

Do NOT simulate training.

While training:

- TRAINING stage becomes active
- show a live processing state
- show contextual DAISY animation
- disable duplicate requests

Do not create fake percentage progress unless the backend actually provides progress information.

After training, display the actual returned results.

==================================================
MODEL RESULTS
==================================================

Create a premium results experience consistent with the existing prototype.

Populate it entirely from backend data.

If the backend returns:

- models
- metrics
- comparison results
- best model
- objective
- training information

display those values.

The winning model must be determined by the backend.

Do not hardcode a winner.

Do not hardcode metric values.

Metrics should adapt to whatever the backend returns.

==================================================
AGENT ACTIVITY
==================================================

Extend the existing UI with an expandable DAISY agent activity/log area.

It should show what DAISY actually did during the current run.

Possible stages:

DATASET
CLEANING
EDA
FEATURE ENGINEERING
TARGET
MODEL SELECTION
TRAINING

Each stage should dynamically show its actual:

- status
- output
- actions
- reasoning
- metrics
- errors

Only display fields that exist.

==================================================
RIGHT-SIDE CONTROL AREA
==================================================

Do not create a permanent dashboard sidebar.

Instead, use the existing DAISY glass/card design language to create a contextual control panel.

The panel should change according to the current pipeline state.

For example:

After upload:
show cleaning action.

After cleaning:
show EDA action.

After EDA:
show feature engineering action.

After feature engineering:
show target selection.

After target:
show model selection.

After model selection:
show training.

After training:
show results.

Only show actions that are currently valid.

==================================================
EXISTING FLOATING CARDS
==================================================

The current landing page contains floating glass cards.

KEEP THEIR STYLE.

However, when entering the live application, transform these cards into dynamic information panels rather than keeping the prototype's fake values.

For example:

Dataset Health card
→ actual dataset state

Active Agent card
→ actual currently running agent

Model card
→ actual training/model result

Training information
→ actual backend result if available

Again:

NO STATIC VALUES.

==================================================
CHAT
==================================================

Keep the existing DAISY "Ask DAISY" interaction.

Connect it to the existing chat backend.

Messages must be real backend responses.

Do not use fake conversations.

The chat should feel like part of the DAISY system, not a separate chatbot product.

==================================================
DOWNLOAD
==================================================

When the processed dataset is available, provide the real dataset download action.

Use the backend download endpoint.

Show appropriate loading/success/error states.

==================================================
API INTEGRATION
==================================================

Create a clean API/service layer.

The frontend should communicate with the existing backend functionality for:

- Dataset upload
- Dataset summary
- Chat
- Data Cleaning Agent
- EDA Agent
- Feature Engineering Agent
- Model Selection Agent
- Model Training Agent
- Processed dataset download

Do not spread API calls throughout visual components.

Keep backend communication isolated and maintainable.

==================================================
STATE MANAGEMENT
==================================================

The application must maintain dynamic state for:

dataset
datasetId
schema
currentStage
cleaningStatus
cleaningResults
edaStatus
edaResults
featureEngineeringStatus
featureEngineeringResults
engineeredColumns
targetColumn
modelSelectionStatus
modelSelectionResults
acceptedModels
rejectedModels
trainingStatus
trainingResults
bestModel
metrics
errors
chat

The UI must react automatically when these states change.

==================================================
NO STATIC RUNTIME CONTENT
==================================================

THIS IS A HARD REQUIREMENT.

Do NOT put placeholder runtime values anywhere.

Do not use:

"4,894 rows"
"98.2%"
"91%"
"2m 14s"
"XGBoost"
"69%"
"12+ agents"
"0 nulls"
or any other example values from the existing prototype.

Those values are visual prototype content only.

Replace runtime information with dynamic backend-driven values.

Static labels such as:

"Dataset Health"
"Active Agent"
"Model Selection"
"Training"
"Ask DAISY"

are completely fine.

But their actual values must be dynamic.

==================================================
IMPORTANT VISUAL RULE
==================================================

The biggest priority is:

KEEP THE EXISTING DESIGN.

Do not turn DAISY into:

sidebar + navbar + KPI cards + generic charts + white tables.

Instead:

Existing DAISY landing page
        ↓
Start a Run
        ↓
Same visual language
        ↓
Live ML workspace
        ↓
Dynamic pipeline
        ↓
Real backend results

It should feel like one continuous product.

The current prototype is the DESIGN SYSTEM.

The backend is the SOURCE OF TRUTH FOR DATA.

Combine both without changing either unnecessarily.

Make the final result feel polished, cinematic, interactive, state-driven, and production-ready.