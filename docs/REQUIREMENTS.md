
# STW Guide – Project Requirements

## 1. Functional Requirements

### FR-01: Condition Search
The system shall allow healthcare professionals to search for an ICMR Standard Treatment Workflow using a medical condition name.

### FR-02: Workflow Retrieval
The system shall retrieve the relevant workflow and display its title, specialty and source information.

### FR-03: Red Flag Identification
The system shall display the red flags associated with the selected condition.

### FR-04: First-Line Management
The system shall provide the first-line management information available in the selected ICMR workflow.

### FR-05: Referral Guidance
The system shall display the referral criteria and appropriate level of care mentioned in the selected workflow.

## 2. Non-Functional Requirements

### NFR-01: Response Time
The API shall respond to document retrieval requests within 2 seconds under normal test conditions.

### NFR-02: Availability
The application shall provide health and readiness endpoints to monitor service status.

### NFR-03: Reliability
The system shall return standardized error responses for invalid requests and unavailable documents.

### NFR-04: Security
The application shall store API credentials in environment variables and must not expose secrets in source code or GitHub.

### NFR-05: Traceability
Every clinical workflow record shall include its source title, publisher and source URL.

## 3. Acceptance Criteria

- Users can retrieve a workflow using its document ID.
- Users can search available workflow records.
- Red flags, first-line management and referral criteria are displayed separately.
- Unsupported clinical questions are not answered using invented information.
- Every workflow includes source attribution.
