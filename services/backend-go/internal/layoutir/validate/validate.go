package validate

import (
	"fmt"

	"github.com/luqing-studio/image-figma/services/backend-go/internal/image/geometry"
	"github.com/luqing-studio/image-figma/services/backend-go/internal/layoutir/contract"
)

type Severity string

const (
	SeverityError   Severity = "error"
	SeverityWarning Severity = "warning"
)

type Finding struct {
	Severity Severity `json:"severity"`
	Code     string   `json:"code"`
	NodeID   string   `json:"nodeId,omitempty"`
	Message  string   `json:"message"`
}

type Report struct {
	Version      string    `json:"version"`
	ErrorCount   int       `json:"errorCount"`
	WarningCount int       `json:"warningCount"`
	Findings     []Finding `json:"findings,omitempty"`
}

func Document(doc contract.Document) Report {
	report := Report{Version: "ui_layout_ir_validation.v1"}
	if doc.Version != contract.Version {
		report.addError("", "LAYOUT_IR_VERSION_INVALID", fmt.Sprintf("expected %s, got %q", contract.Version, doc.Version))
	}
	if doc.SourceImage.Width <= 0 || doc.SourceImage.Height <= 0 {
		report.addError("", "LAYOUT_IR_SOURCE_IMAGE_INVALID", "source image width and height must be positive")
	}

	assetIDs := map[string]bool{}
	for _, asset := range doc.Assets {
		if asset.ID == "" {
			report.addError("", "LAYOUT_IR_ASSET_ID_MISSING", "asset id is required")
			continue
		}
		if assetIDs[asset.ID] {
			report.addError("", "LAYOUT_IR_ASSET_ID_DUPLICATE", fmt.Sprintf("duplicate asset id %q", asset.ID))
		}
		assetIDs[asset.ID] = true
	}

	ids := map[string]bool{}
	validateNode(&report, doc.Root, true, geometry.Rect{Width: doc.SourceImage.Width, Height: doc.SourceImage.Height}, ids, assetIDs)

	for _, decision := range doc.Decisions {
		if decision.ID == "" {
			report.addError("", "LAYOUT_IR_DECISION_ID_MISSING", "decision id is required")
		}
		if !validDecisionState(decision.State) {
			report.addError(decision.NodeID, "LAYOUT_IR_DECISION_STATE_INVALID", fmt.Sprintf("invalid decision state %q", decision.State))
		}
		if decision.Reason == "" {
			report.addError(decision.NodeID, "LAYOUT_IR_DECISION_REASON_MISSING", "decision reason is required")
		}
	}
	for _, evidence := range doc.Evidence {
		if evidence.ID == "" {
			report.addError("", "LAYOUT_IR_EVIDENCE_ID_MISSING", "evidence id is required")
		}
		if evidence.Kind == "" {
			report.addError("", "LAYOUT_IR_EVIDENCE_KIND_MISSING", "evidence kind is required")
		}
		if evidence.Source == "" {
			report.addError("", "LAYOUT_IR_EVIDENCE_SOURCE_MISSING", "evidence source is required")
		}
		if evidence.BBox.Area() <= 0 {
			report.addError("", "LAYOUT_IR_EVIDENCE_BBOX_INVALID", "evidence bbox must have positive area")
		}
		if len(evidence.SourceRefs) == 0 {
			report.addError("", "LAYOUT_IR_EVIDENCE_SOURCE_REFS_MISSING", "evidence sourceRefs are required")
		}
	}

	return report
}

func validateNode(report *Report, node contract.Node, isRoot bool, bounds geometry.Rect, ids map[string]bool, assetIDs map[string]bool) {
	if node.ID == "" {
		report.addError("", "LAYOUT_IR_NODE_ID_MISSING", "node id is required")
	} else if ids[node.ID] {
		report.addError(node.ID, "LAYOUT_IR_NODE_ID_DUPLICATE", fmt.Sprintf("duplicate node id %q", node.ID))
	}
	ids[node.ID] = true

	if !validNodeType(node.Type) {
		report.addError(node.ID, "LAYOUT_IR_NODE_TYPE_INVALID", fmt.Sprintf("invalid node type %q", node.Type))
	}
	if isRoot && node.Type != contract.NodePage {
		report.addError(node.ID, "LAYOUT_IR_ROOT_TYPE_INVALID", "root node must have type page")
	}
	if !validLayoutMode(node.Layout.Mode) {
		report.addError(node.ID, "LAYOUT_IR_LAYOUT_MODE_INVALID", fmt.Sprintf("invalid layout mode %q", node.Layout.Mode))
	}
	if node.BBox.Area() <= 0 {
		report.addError(node.ID, "LAYOUT_IR_NODE_BBOX_INVALID", "node bbox must have positive area")
	}
	if isRoot && bounds.Area() > 0 && node.BBox != bounds {
		report.addError(node.ID, "LAYOUT_IR_ROOT_BBOX_INVALID", "root bbox must match source image bounds")
	}
	if bounds.Area() > 0 && geometry.IoA(node.BBox, bounds) < 1 {
		report.addError(node.ID, "LAYOUT_IR_NODE_BBOX_OUT_OF_BOUNDS", "node bbox must stay inside source image bounds")
	}
	if len(node.SourceRefs) == 0 {
		report.addError(node.ID, "LAYOUT_IR_NODE_SOURCE_REFS_MISSING", "node sourceRefs are required")
	}
	if requiresAsset(node.Type) {
		if node.AssetRef == nil || node.AssetRef.AssetID == "" {
			report.addError(node.ID, "LAYOUT_IR_NODE_ASSET_REF_MISSING", "image/icon/crop node requires assetRef.assetId")
		} else if !assetIDs[node.AssetRef.AssetID] {
			report.addError(node.ID, "LAYOUT_IR_NODE_ASSET_NOT_FOUND", fmt.Sprintf("asset %q was not declared", node.AssetRef.AssetID))
		}
	}
	if node.Type == contract.NodeText && (node.Text == nil || node.Text.Characters == "") {
		report.addError(node.ID, "LAYOUT_IR_TEXT_MISSING", "text node requires non-empty text.characters")
	}

	for _, child := range node.Children {
		validateNode(report, child, false, bounds, ids, assetIDs)
	}
}

func validNodeType(value contract.NodeType) bool {
	switch value {
	case contract.NodePage, contract.NodeSection, contract.NodeRow, contract.NodeColumn, contract.NodeGroup, contract.NodeOverlay,
		contract.NodeText, contract.NodeImage, contract.NodeShape, contract.NodeIcon, contract.NodeUnknownCrop:
		return true
	default:
		return false
	}
}

func validLayoutMode(value contract.LayoutMode) bool {
	switch value {
	case contract.LayoutAbsolute, contract.LayoutRow, contract.LayoutColumn, contract.LayoutOverlay:
		return true
	default:
		return false
	}
}

func validDecisionState(value contract.DecisionState) bool {
	switch value {
	case contract.DecisionEmit, contract.DecisionGroup, contract.DecisionSplit, contract.DecisionMerge, contract.DecisionSuppress,
		contract.DecisionFallbackCrop, contract.DecisionPromoteText, contract.DecisionPromoteImage, contract.DecisionReferenceOnly:
		return true
	default:
		return false
	}
}

func requiresAsset(value contract.NodeType) bool {
	return value == contract.NodeImage || value == contract.NodeIcon || value == contract.NodeUnknownCrop
}

func (r *Report) addError(nodeID string, code string, message string) {
	r.ErrorCount++
	r.Findings = append(r.Findings, Finding{
		Severity: SeverityError,
		Code:     code,
		NodeID:   nodeID,
		Message:  message,
	})
}
