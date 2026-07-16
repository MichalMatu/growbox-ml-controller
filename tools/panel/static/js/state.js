/* Shared mutable state — var for cross-script visibility in classic <script> tags. */
var panelSchema = null;
var scenario = {};
var lastDecision = null;
var lastState = null;
var deviceScenarioSynced = false;
var deviceScenarioBaseline = null;
var activeModal = "scenario";
var modalReturnFocus = null;
var helpReturnFocus = null;
var lastRenderedDecisionStep = null;
var lastRenderedPreviousStep = null;
var previousDisplaySnapshot = null;
var connectFailureMessage = null;
var connectFailureDetail = null;
var topBarMessageItems = [];
var portCatalog = [];
var selectedPortDevice = "";
