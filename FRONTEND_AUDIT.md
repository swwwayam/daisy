# Frontend audit and fixes

Reviewed the active React entry point, landing navigation, authentication,
workspace stages, history, profile, prediction and explanation panels against
the Web Interface Guidelines. Existing black/violet DAISY styling is preserved.

## Fixed

- Upload error Retry referenced an input that had been unmounted. The error state
  now keeps the file picker available; file selection remains keyboard accessible.
- Authentication and workspace views were only in React state. Hash locations
  now support login/workspace reloads and Back navigation, with unauthenticated
  workspace links redirected to sign-in.
- Google login exceptions could leave the button busy. They now show a retryable
  message. Sign-out errors are surfaced rather than silently leaving the view.
- A prolonged initial session request had no recovery control. After 12 seconds
  it offers connection retry and public-site browsing.
- Missing deployment settings and component rendering failures could produce a
  blank screen. Configuration and render recovery screens now provide a next action.
- Target filtering lacked a label and no-match feedback. Both are present.
- Cancel-training errors were unhandled. The action now prevents duplicate clicks
  and shows failures. Final evaluation errors no longer show duplicate action panels.
- Confusion matrix rows/columns had no axis meaning. Actual and predicted classes
  are now labeled with column/row headers.
- Homepage counts said six stages and ten models. They now match eight and 27.
- Added a signed-in profile dialog with initials, email, verification state,
  joined date, editable display name and sign-out. Identity and updates use the
  existing Better Auth session. Browser modal focus/Escape behavior is retained.
  A native cursor is restored inside the top-layer dialog so the custom cursor
  cannot disappear behind it.
- Added accessible EDA, validation-candidate, permutation and SHAP visualizations.
  Numeric values accompany color and bars. Feature lists are height-bounded.

## Verification and limits

TypeScript and a build with local development settings, 323 passing backend tests
(including SHAP/additivity and owner boundaries), and browser checks of the landing-to-login flow were performed. A production build correctly rejects the local
HTTP backend URL; a deployed HTTPS API endpoint is still needed. Profile
editing, save feedback, modal closing and chart layout were exercised with a
temporary synthetic UI fixture; that fixture is removed after inspection. The
fixture does not establish that a real account update or Google login passed.
Live authenticated profile persistence and OAuth still require a user-owned
browser walkthrough. SHAP is limited to the supported tree families; permutation
importance remains available for other models. The production build retains
Vite's existing large-chunk advisory for Three.js and the main client bundle.
