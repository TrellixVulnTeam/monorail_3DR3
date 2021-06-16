// Code generated by protoc-gen-go. DO NOT EDIT.
// source: api/api_proto/project_objects.proto

package monorail

import (
	fmt "fmt"
	proto "github.com/golang/protobuf/proto"
	math "math"
)

// Reference imports to suppress errors if they are not otherwise used.
var _ = proto.Marshal
var _ = fmt.Errorf
var _ = math.Inf

// This is a compile-time assertion to ensure that this generated file
// is compatible with the proto package it is being compiled against.
// A compilation error at this line likely means your copy of the
// proto package needs to be updated.
const _ = proto.ProtoPackageIsVersion3 // please upgrade the proto package

// Next available tag: 4
type Project struct {
	Name                 string   `protobuf:"bytes,1,opt,name=name,proto3" json:"name,omitempty"`
	Summary              string   `protobuf:"bytes,2,opt,name=summary,proto3" json:"summary,omitempty"`
	Description          string   `protobuf:"bytes,3,opt,name=description,proto3" json:"description,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *Project) Reset()         { *m = Project{} }
func (m *Project) String() string { return proto.CompactTextString(m) }
func (*Project) ProtoMessage()    {}
func (*Project) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{0}
}

func (m *Project) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Project.Unmarshal(m, b)
}
func (m *Project) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Project.Marshal(b, m, deterministic)
}
func (m *Project) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Project.Merge(m, src)
}
func (m *Project) XXX_Size() int {
	return xxx_messageInfo_Project.Size(m)
}
func (m *Project) XXX_DiscardUnknown() {
	xxx_messageInfo_Project.DiscardUnknown(m)
}

var xxx_messageInfo_Project proto.InternalMessageInfo

func (m *Project) GetName() string {
	if m != nil {
		return m.Name
	}
	return ""
}

func (m *Project) GetSummary() string {
	if m != nil {
		return m.Summary
	}
	return ""
}

func (m *Project) GetDescription() string {
	if m != nil {
		return m.Description
	}
	return ""
}

// Next available tag: 6
type StatusDef struct {
	Status               string   `protobuf:"bytes,1,opt,name=status,proto3" json:"status,omitempty"`
	MeansOpen            bool     `protobuf:"varint,2,opt,name=means_open,json=meansOpen,proto3" json:"means_open,omitempty"`
	Rank                 uint32   `protobuf:"varint,3,opt,name=rank,proto3" json:"rank,omitempty"`
	Docstring            string   `protobuf:"bytes,4,opt,name=docstring,proto3" json:"docstring,omitempty"`
	Deprecated           bool     `protobuf:"varint,5,opt,name=deprecated,proto3" json:"deprecated,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *StatusDef) Reset()         { *m = StatusDef{} }
func (m *StatusDef) String() string { return proto.CompactTextString(m) }
func (*StatusDef) ProtoMessage()    {}
func (*StatusDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{1}
}

func (m *StatusDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_StatusDef.Unmarshal(m, b)
}
func (m *StatusDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_StatusDef.Marshal(b, m, deterministic)
}
func (m *StatusDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_StatusDef.Merge(m, src)
}
func (m *StatusDef) XXX_Size() int {
	return xxx_messageInfo_StatusDef.Size(m)
}
func (m *StatusDef) XXX_DiscardUnknown() {
	xxx_messageInfo_StatusDef.DiscardUnknown(m)
}

var xxx_messageInfo_StatusDef proto.InternalMessageInfo

func (m *StatusDef) GetStatus() string {
	if m != nil {
		return m.Status
	}
	return ""
}

func (m *StatusDef) GetMeansOpen() bool {
	if m != nil {
		return m.MeansOpen
	}
	return false
}

func (m *StatusDef) GetRank() uint32 {
	if m != nil {
		return m.Rank
	}
	return 0
}

func (m *StatusDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *StatusDef) GetDeprecated() bool {
	if m != nil {
		return m.Deprecated
	}
	return false
}

// Next available tag: 5
type LabelDef struct {
	Label                string   `protobuf:"bytes,1,opt,name=label,proto3" json:"label,omitempty"`
	Docstring            string   `protobuf:"bytes,3,opt,name=docstring,proto3" json:"docstring,omitempty"`
	Deprecated           bool     `protobuf:"varint,4,opt,name=deprecated,proto3" json:"deprecated,omitempty"`
	XXX_NoUnkeyedLiteral struct{} `json:"-"`
	XXX_unrecognized     []byte   `json:"-"`
	XXX_sizecache        int32    `json:"-"`
}

func (m *LabelDef) Reset()         { *m = LabelDef{} }
func (m *LabelDef) String() string { return proto.CompactTextString(m) }
func (*LabelDef) ProtoMessage()    {}
func (*LabelDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{2}
}

func (m *LabelDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_LabelDef.Unmarshal(m, b)
}
func (m *LabelDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_LabelDef.Marshal(b, m, deterministic)
}
func (m *LabelDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_LabelDef.Merge(m, src)
}
func (m *LabelDef) XXX_Size() int {
	return xxx_messageInfo_LabelDef.Size(m)
}
func (m *LabelDef) XXX_DiscardUnknown() {
	xxx_messageInfo_LabelDef.DiscardUnknown(m)
}

var xxx_messageInfo_LabelDef proto.InternalMessageInfo

func (m *LabelDef) GetLabel() string {
	if m != nil {
		return m.Label
	}
	return ""
}

func (m *LabelDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *LabelDef) GetDeprecated() bool {
	if m != nil {
		return m.Deprecated
	}
	return false
}

// Next available tag: 11
type ComponentDef struct {
	Path                 string      `protobuf:"bytes,1,opt,name=path,proto3" json:"path,omitempty"`
	Docstring            string      `protobuf:"bytes,2,opt,name=docstring,proto3" json:"docstring,omitempty"`
	AdminRefs            []*UserRef  `protobuf:"bytes,3,rep,name=admin_refs,json=adminRefs,proto3" json:"admin_refs,omitempty"`
	CcRefs               []*UserRef  `protobuf:"bytes,4,rep,name=cc_refs,json=ccRefs,proto3" json:"cc_refs,omitempty"`
	Deprecated           bool        `protobuf:"varint,5,opt,name=deprecated,proto3" json:"deprecated,omitempty"`
	Created              uint32      `protobuf:"fixed32,6,opt,name=created,proto3" json:"created,omitempty"`
	CreatorRef           *UserRef    `protobuf:"bytes,7,opt,name=creator_ref,json=creatorRef,proto3" json:"creator_ref,omitempty"`
	Modified             uint32      `protobuf:"fixed32,8,opt,name=modified,proto3" json:"modified,omitempty"`
	ModifierRef          *UserRef    `protobuf:"bytes,9,opt,name=modifier_ref,json=modifierRef,proto3" json:"modifier_ref,omitempty"`
	LabelRefs            []*LabelRef `protobuf:"bytes,10,rep,name=label_refs,json=labelRefs,proto3" json:"label_refs,omitempty"`
	XXX_NoUnkeyedLiteral struct{}    `json:"-"`
	XXX_unrecognized     []byte      `json:"-"`
	XXX_sizecache        int32       `json:"-"`
}

func (m *ComponentDef) Reset()         { *m = ComponentDef{} }
func (m *ComponentDef) String() string { return proto.CompactTextString(m) }
func (*ComponentDef) ProtoMessage()    {}
func (*ComponentDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{3}
}

func (m *ComponentDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ComponentDef.Unmarshal(m, b)
}
func (m *ComponentDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ComponentDef.Marshal(b, m, deterministic)
}
func (m *ComponentDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ComponentDef.Merge(m, src)
}
func (m *ComponentDef) XXX_Size() int {
	return xxx_messageInfo_ComponentDef.Size(m)
}
func (m *ComponentDef) XXX_DiscardUnknown() {
	xxx_messageInfo_ComponentDef.DiscardUnknown(m)
}

var xxx_messageInfo_ComponentDef proto.InternalMessageInfo

func (m *ComponentDef) GetPath() string {
	if m != nil {
		return m.Path
	}
	return ""
}

func (m *ComponentDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *ComponentDef) GetAdminRefs() []*UserRef {
	if m != nil {
		return m.AdminRefs
	}
	return nil
}

func (m *ComponentDef) GetCcRefs() []*UserRef {
	if m != nil {
		return m.CcRefs
	}
	return nil
}

func (m *ComponentDef) GetDeprecated() bool {
	if m != nil {
		return m.Deprecated
	}
	return false
}

func (m *ComponentDef) GetCreated() uint32 {
	if m != nil {
		return m.Created
	}
	return 0
}

func (m *ComponentDef) GetCreatorRef() *UserRef {
	if m != nil {
		return m.CreatorRef
	}
	return nil
}

func (m *ComponentDef) GetModified() uint32 {
	if m != nil {
		return m.Modified
	}
	return 0
}

func (m *ComponentDef) GetModifierRef() *UserRef {
	if m != nil {
		return m.ModifierRef
	}
	return nil
}

func (m *ComponentDef) GetLabelRefs() []*LabelRef {
	if m != nil {
		return m.LabelRefs
	}
	return nil
}

// Next available tag: 9
type FieldDef struct {
	FieldRef       *FieldRef `protobuf:"bytes,1,opt,name=field_ref,json=fieldRef,proto3" json:"field_ref,omitempty"`
	ApplicableType string    `protobuf:"bytes,2,opt,name=applicable_type,json=applicableType,proto3" json:"applicable_type,omitempty"`
	// TODO(jrobbins): applicable_predicate
	IsRequired    bool       `protobuf:"varint,3,opt,name=is_required,json=isRequired,proto3" json:"is_required,omitempty"`
	IsNiche       bool       `protobuf:"varint,4,opt,name=is_niche,json=isNiche,proto3" json:"is_niche,omitempty"`
	IsMultivalued bool       `protobuf:"varint,5,opt,name=is_multivalued,json=isMultivalued,proto3" json:"is_multivalued,omitempty"`
	Docstring     string     `protobuf:"bytes,6,opt,name=docstring,proto3" json:"docstring,omitempty"`
	AdminRefs     []*UserRef `protobuf:"bytes,7,rep,name=admin_refs,json=adminRefs,proto3" json:"admin_refs,omitempty"`
	// TODO(jrobbins): validation, permission granting, and notification options.
	IsPhaseField         bool        `protobuf:"varint,8,opt,name=is_phase_field,json=isPhaseField,proto3" json:"is_phase_field,omitempty"`
	UserChoices          []*UserRef  `protobuf:"bytes,9,rep,name=user_choices,json=userChoices,proto3" json:"user_choices,omitempty"`
	EnumChoices          []*LabelDef `protobuf:"bytes,10,rep,name=enum_choices,json=enumChoices,proto3" json:"enum_choices,omitempty"`
	XXX_NoUnkeyedLiteral struct{}    `json:"-"`
	XXX_unrecognized     []byte      `json:"-"`
	XXX_sizecache        int32       `json:"-"`
}

func (m *FieldDef) Reset()         { *m = FieldDef{} }
func (m *FieldDef) String() string { return proto.CompactTextString(m) }
func (*FieldDef) ProtoMessage()    {}
func (*FieldDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{4}
}

func (m *FieldDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_FieldDef.Unmarshal(m, b)
}
func (m *FieldDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_FieldDef.Marshal(b, m, deterministic)
}
func (m *FieldDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_FieldDef.Merge(m, src)
}
func (m *FieldDef) XXX_Size() int {
	return xxx_messageInfo_FieldDef.Size(m)
}
func (m *FieldDef) XXX_DiscardUnknown() {
	xxx_messageInfo_FieldDef.DiscardUnknown(m)
}

var xxx_messageInfo_FieldDef proto.InternalMessageInfo

func (m *FieldDef) GetFieldRef() *FieldRef {
	if m != nil {
		return m.FieldRef
	}
	return nil
}

func (m *FieldDef) GetApplicableType() string {
	if m != nil {
		return m.ApplicableType
	}
	return ""
}

func (m *FieldDef) GetIsRequired() bool {
	if m != nil {
		return m.IsRequired
	}
	return false
}

func (m *FieldDef) GetIsNiche() bool {
	if m != nil {
		return m.IsNiche
	}
	return false
}

func (m *FieldDef) GetIsMultivalued() bool {
	if m != nil {
		return m.IsMultivalued
	}
	return false
}

func (m *FieldDef) GetDocstring() string {
	if m != nil {
		return m.Docstring
	}
	return ""
}

func (m *FieldDef) GetAdminRefs() []*UserRef {
	if m != nil {
		return m.AdminRefs
	}
	return nil
}

func (m *FieldDef) GetIsPhaseField() bool {
	if m != nil {
		return m.IsPhaseField
	}
	return false
}

func (m *FieldDef) GetUserChoices() []*UserRef {
	if m != nil {
		return m.UserChoices
	}
	return nil
}

func (m *FieldDef) GetEnumChoices() []*LabelDef {
	if m != nil {
		return m.EnumChoices
	}
	return nil
}

// Next available tag: 3
type FieldOptions struct {
	FieldRef             *FieldRef  `protobuf:"bytes,1,opt,name=field_ref,json=fieldRef,proto3" json:"field_ref,omitempty"`
	UserRefs             []*UserRef `protobuf:"bytes,2,rep,name=user_refs,json=userRefs,proto3" json:"user_refs,omitempty"`
	XXX_NoUnkeyedLiteral struct{}   `json:"-"`
	XXX_unrecognized     []byte     `json:"-"`
	XXX_sizecache        int32      `json:"-"`
}

func (m *FieldOptions) Reset()         { *m = FieldOptions{} }
func (m *FieldOptions) String() string { return proto.CompactTextString(m) }
func (*FieldOptions) ProtoMessage()    {}
func (*FieldOptions) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{5}
}

func (m *FieldOptions) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_FieldOptions.Unmarshal(m, b)
}
func (m *FieldOptions) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_FieldOptions.Marshal(b, m, deterministic)
}
func (m *FieldOptions) XXX_Merge(src proto.Message) {
	xxx_messageInfo_FieldOptions.Merge(m, src)
}
func (m *FieldOptions) XXX_Size() int {
	return xxx_messageInfo_FieldOptions.Size(m)
}
func (m *FieldOptions) XXX_DiscardUnknown() {
	xxx_messageInfo_FieldOptions.DiscardUnknown(m)
}

var xxx_messageInfo_FieldOptions proto.InternalMessageInfo

func (m *FieldOptions) GetFieldRef() *FieldRef {
	if m != nil {
		return m.FieldRef
	}
	return nil
}

func (m *FieldOptions) GetUserRefs() []*UserRef {
	if m != nil {
		return m.UserRefs
	}
	return nil
}

// Next available tag: 4
type ApprovalDef struct {
	FieldRef             *FieldRef  `protobuf:"bytes,1,opt,name=field_ref,json=fieldRef,proto3" json:"field_ref,omitempty"`
	ApproverRefs         []*UserRef `protobuf:"bytes,2,rep,name=approver_refs,json=approverRefs,proto3" json:"approver_refs,omitempty"`
	Survey               string     `protobuf:"bytes,3,opt,name=survey,proto3" json:"survey,omitempty"`
	XXX_NoUnkeyedLiteral struct{}   `json:"-"`
	XXX_unrecognized     []byte     `json:"-"`
	XXX_sizecache        int32      `json:"-"`
}

func (m *ApprovalDef) Reset()         { *m = ApprovalDef{} }
func (m *ApprovalDef) String() string { return proto.CompactTextString(m) }
func (*ApprovalDef) ProtoMessage()    {}
func (*ApprovalDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{6}
}

func (m *ApprovalDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_ApprovalDef.Unmarshal(m, b)
}
func (m *ApprovalDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_ApprovalDef.Marshal(b, m, deterministic)
}
func (m *ApprovalDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_ApprovalDef.Merge(m, src)
}
func (m *ApprovalDef) XXX_Size() int {
	return xxx_messageInfo_ApprovalDef.Size(m)
}
func (m *ApprovalDef) XXX_DiscardUnknown() {
	xxx_messageInfo_ApprovalDef.DiscardUnknown(m)
}

var xxx_messageInfo_ApprovalDef proto.InternalMessageInfo

func (m *ApprovalDef) GetFieldRef() *FieldRef {
	if m != nil {
		return m.FieldRef
	}
	return nil
}

func (m *ApprovalDef) GetApproverRefs() []*UserRef {
	if m != nil {
		return m.ApproverRefs
	}
	return nil
}

func (m *ApprovalDef) GetSurvey() string {
	if m != nil {
		return m.Survey
	}
	return ""
}

// Next available tag: 11
type Config struct {
	ProjectName            string          `protobuf:"bytes,1,opt,name=project_name,json=projectName,proto3" json:"project_name,omitempty"`
	StatusDefs             []*StatusDef    `protobuf:"bytes,2,rep,name=status_defs,json=statusDefs,proto3" json:"status_defs,omitempty"`
	StatusesOfferMerge     []*StatusRef    `protobuf:"bytes,3,rep,name=statuses_offer_merge,json=statusesOfferMerge,proto3" json:"statuses_offer_merge,omitempty"`
	LabelDefs              []*LabelDef     `protobuf:"bytes,4,rep,name=label_defs,json=labelDefs,proto3" json:"label_defs,omitempty"`
	ExclusiveLabelPrefixes []string        `protobuf:"bytes,5,rep,name=exclusive_label_prefixes,json=exclusiveLabelPrefixes,proto3" json:"exclusive_label_prefixes,omitempty"`
	ComponentDefs          []*ComponentDef `protobuf:"bytes,6,rep,name=component_defs,json=componentDefs,proto3" json:"component_defs,omitempty"`
	FieldDefs              []*FieldDef     `protobuf:"bytes,7,rep,name=field_defs,json=fieldDefs,proto3" json:"field_defs,omitempty"`
	ApprovalDefs           []*ApprovalDef  `protobuf:"bytes,8,rep,name=approval_defs,json=approvalDefs,proto3" json:"approval_defs,omitempty"`
	RestrictToKnown        bool            `protobuf:"varint,9,opt,name=restrict_to_known,json=restrictToKnown,proto3" json:"restrict_to_known,omitempty"`
	XXX_NoUnkeyedLiteral   struct{}        `json:"-"`
	XXX_unrecognized       []byte          `json:"-"`
	XXX_sizecache          int32           `json:"-"`
}

func (m *Config) Reset()         { *m = Config{} }
func (m *Config) String() string { return proto.CompactTextString(m) }
func (*Config) ProtoMessage()    {}
func (*Config) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{7}
}

func (m *Config) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_Config.Unmarshal(m, b)
}
func (m *Config) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_Config.Marshal(b, m, deterministic)
}
func (m *Config) XXX_Merge(src proto.Message) {
	xxx_messageInfo_Config.Merge(m, src)
}
func (m *Config) XXX_Size() int {
	return xxx_messageInfo_Config.Size(m)
}
func (m *Config) XXX_DiscardUnknown() {
	xxx_messageInfo_Config.DiscardUnknown(m)
}

var xxx_messageInfo_Config proto.InternalMessageInfo

func (m *Config) GetProjectName() string {
	if m != nil {
		return m.ProjectName
	}
	return ""
}

func (m *Config) GetStatusDefs() []*StatusDef {
	if m != nil {
		return m.StatusDefs
	}
	return nil
}

func (m *Config) GetStatusesOfferMerge() []*StatusRef {
	if m != nil {
		return m.StatusesOfferMerge
	}
	return nil
}

func (m *Config) GetLabelDefs() []*LabelDef {
	if m != nil {
		return m.LabelDefs
	}
	return nil
}

func (m *Config) GetExclusiveLabelPrefixes() []string {
	if m != nil {
		return m.ExclusiveLabelPrefixes
	}
	return nil
}

func (m *Config) GetComponentDefs() []*ComponentDef {
	if m != nil {
		return m.ComponentDefs
	}
	return nil
}

func (m *Config) GetFieldDefs() []*FieldDef {
	if m != nil {
		return m.FieldDefs
	}
	return nil
}

func (m *Config) GetApprovalDefs() []*ApprovalDef {
	if m != nil {
		return m.ApprovalDefs
	}
	return nil
}

func (m *Config) GetRestrictToKnown() bool {
	if m != nil {
		return m.RestrictToKnown
	}
	return false
}

// Next available tag: 11
type PresentationConfig struct {
	ProjectThumbnailUrl  string        `protobuf:"bytes,1,opt,name=project_thumbnail_url,json=projectThumbnailUrl,proto3" json:"project_thumbnail_url,omitempty"`
	ProjectSummary       string        `protobuf:"bytes,2,opt,name=project_summary,json=projectSummary,proto3" json:"project_summary,omitempty"`
	CustomIssueEntryUrl  string        `protobuf:"bytes,3,opt,name=custom_issue_entry_url,json=customIssueEntryUrl,proto3" json:"custom_issue_entry_url,omitempty"`
	DefaultQuery         string        `protobuf:"bytes,4,opt,name=default_query,json=defaultQuery,proto3" json:"default_query,omitempty"`
	SavedQueries         []*SavedQuery `protobuf:"bytes,5,rep,name=saved_queries,json=savedQueries,proto3" json:"saved_queries,omitempty"`
	RevisionUrlFormat    string        `protobuf:"bytes,6,opt,name=revision_url_format,json=revisionUrlFormat,proto3" json:"revision_url_format,omitempty"`
	DefaultColSpec       string        `protobuf:"bytes,7,opt,name=default_col_spec,json=defaultColSpec,proto3" json:"default_col_spec,omitempty"`
	DefaultSortSpec      string        `protobuf:"bytes,8,opt,name=default_sort_spec,json=defaultSortSpec,proto3" json:"default_sort_spec,omitempty"`
	DefaultXAttr         string        `protobuf:"bytes,9,opt,name=default_x_attr,json=defaultXAttr,proto3" json:"default_x_attr,omitempty"`
	DefaultYAttr         string        `protobuf:"bytes,10,opt,name=default_y_attr,json=defaultYAttr,proto3" json:"default_y_attr,omitempty"`
	XXX_NoUnkeyedLiteral struct{}      `json:"-"`
	XXX_unrecognized     []byte        `json:"-"`
	XXX_sizecache        int32         `json:"-"`
}

func (m *PresentationConfig) Reset()         { *m = PresentationConfig{} }
func (m *PresentationConfig) String() string { return proto.CompactTextString(m) }
func (*PresentationConfig) ProtoMessage()    {}
func (*PresentationConfig) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{8}
}

func (m *PresentationConfig) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_PresentationConfig.Unmarshal(m, b)
}
func (m *PresentationConfig) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_PresentationConfig.Marshal(b, m, deterministic)
}
func (m *PresentationConfig) XXX_Merge(src proto.Message) {
	xxx_messageInfo_PresentationConfig.Merge(m, src)
}
func (m *PresentationConfig) XXX_Size() int {
	return xxx_messageInfo_PresentationConfig.Size(m)
}
func (m *PresentationConfig) XXX_DiscardUnknown() {
	xxx_messageInfo_PresentationConfig.DiscardUnknown(m)
}

var xxx_messageInfo_PresentationConfig proto.InternalMessageInfo

func (m *PresentationConfig) GetProjectThumbnailUrl() string {
	if m != nil {
		return m.ProjectThumbnailUrl
	}
	return ""
}

func (m *PresentationConfig) GetProjectSummary() string {
	if m != nil {
		return m.ProjectSummary
	}
	return ""
}

func (m *PresentationConfig) GetCustomIssueEntryUrl() string {
	if m != nil {
		return m.CustomIssueEntryUrl
	}
	return ""
}

func (m *PresentationConfig) GetDefaultQuery() string {
	if m != nil {
		return m.DefaultQuery
	}
	return ""
}

func (m *PresentationConfig) GetSavedQueries() []*SavedQuery {
	if m != nil {
		return m.SavedQueries
	}
	return nil
}

func (m *PresentationConfig) GetRevisionUrlFormat() string {
	if m != nil {
		return m.RevisionUrlFormat
	}
	return ""
}

func (m *PresentationConfig) GetDefaultColSpec() string {
	if m != nil {
		return m.DefaultColSpec
	}
	return ""
}

func (m *PresentationConfig) GetDefaultSortSpec() string {
	if m != nil {
		return m.DefaultSortSpec
	}
	return ""
}

func (m *PresentationConfig) GetDefaultXAttr() string {
	if m != nil {
		return m.DefaultXAttr
	}
	return ""
}

func (m *PresentationConfig) GetDefaultYAttr() string {
	if m != nil {
		return m.DefaultYAttr
	}
	return ""
}

// Next available tag: 16
type TemplateDef struct {
	TemplateName          string          `protobuf:"bytes,1,opt,name=template_name,json=templateName,proto3" json:"template_name,omitempty"`
	Content               string          `protobuf:"bytes,2,opt,name=content,proto3" json:"content,omitempty"`
	Summary               string          `protobuf:"bytes,3,opt,name=summary,proto3" json:"summary,omitempty"`
	SummaryMustBeEdited   bool            `protobuf:"varint,4,opt,name=summary_must_be_edited,json=summaryMustBeEdited,proto3" json:"summary_must_be_edited,omitempty"`
	OwnerRef              *UserRef        `protobuf:"bytes,5,opt,name=owner_ref,json=ownerRef,proto3" json:"owner_ref,omitempty"`
	StatusRef             *StatusRef      `protobuf:"bytes,6,opt,name=status_ref,json=statusRef,proto3" json:"status_ref,omitempty"`
	LabelRefs             []*LabelRef     `protobuf:"bytes,7,rep,name=label_refs,json=labelRefs,proto3" json:"label_refs,omitempty"`
	MembersOnly           bool            `protobuf:"varint,8,opt,name=members_only,json=membersOnly,proto3" json:"members_only,omitempty"`
	OwnerDefaultsToMember bool            `protobuf:"varint,9,opt,name=owner_defaults_to_member,json=ownerDefaultsToMember,proto3" json:"owner_defaults_to_member,omitempty"`
	AdminRefs             []*UserRef      `protobuf:"bytes,10,rep,name=admin_refs,json=adminRefs,proto3" json:"admin_refs,omitempty"`
	FieldValues           []*FieldValue   `protobuf:"bytes,11,rep,name=field_values,json=fieldValues,proto3" json:"field_values,omitempty"`
	ComponentRefs         []*ComponentRef `protobuf:"bytes,12,rep,name=component_refs,json=componentRefs,proto3" json:"component_refs,omitempty"`
	ComponentRequired     bool            `protobuf:"varint,13,opt,name=component_required,json=componentRequired,proto3" json:"component_required,omitempty"`
	ApprovalValues        []*Approval     `protobuf:"bytes,14,rep,name=approval_values,json=approvalValues,proto3" json:"approval_values,omitempty"`
	Phases                []*PhaseDef     `protobuf:"bytes,15,rep,name=phases,proto3" json:"phases,omitempty"`
	XXX_NoUnkeyedLiteral  struct{}        `json:"-"`
	XXX_unrecognized      []byte          `json:"-"`
	XXX_sizecache         int32           `json:"-"`
}

func (m *TemplateDef) Reset()         { *m = TemplateDef{} }
func (m *TemplateDef) String() string { return proto.CompactTextString(m) }
func (*TemplateDef) ProtoMessage()    {}
func (*TemplateDef) Descriptor() ([]byte, []int) {
	return fileDescriptor_4f680a8ed8804f88, []int{9}
}

func (m *TemplateDef) XXX_Unmarshal(b []byte) error {
	return xxx_messageInfo_TemplateDef.Unmarshal(m, b)
}
func (m *TemplateDef) XXX_Marshal(b []byte, deterministic bool) ([]byte, error) {
	return xxx_messageInfo_TemplateDef.Marshal(b, m, deterministic)
}
func (m *TemplateDef) XXX_Merge(src proto.Message) {
	xxx_messageInfo_TemplateDef.Merge(m, src)
}
func (m *TemplateDef) XXX_Size() int {
	return xxx_messageInfo_TemplateDef.Size(m)
}
func (m *TemplateDef) XXX_DiscardUnknown() {
	xxx_messageInfo_TemplateDef.DiscardUnknown(m)
}

var xxx_messageInfo_TemplateDef proto.InternalMessageInfo

func (m *TemplateDef) GetTemplateName() string {
	if m != nil {
		return m.TemplateName
	}
	return ""
}

func (m *TemplateDef) GetContent() string {
	if m != nil {
		return m.Content
	}
	return ""
}

func (m *TemplateDef) GetSummary() string {
	if m != nil {
		return m.Summary
	}
	return ""
}

func (m *TemplateDef) GetSummaryMustBeEdited() bool {
	if m != nil {
		return m.SummaryMustBeEdited
	}
	return false
}

func (m *TemplateDef) GetOwnerRef() *UserRef {
	if m != nil {
		return m.OwnerRef
	}
	return nil
}

func (m *TemplateDef) GetStatusRef() *StatusRef {
	if m != nil {
		return m.StatusRef
	}
	return nil
}

func (m *TemplateDef) GetLabelRefs() []*LabelRef {
	if m != nil {
		return m.LabelRefs
	}
	return nil
}

func (m *TemplateDef) GetMembersOnly() bool {
	if m != nil {
		return m.MembersOnly
	}
	return false
}

func (m *TemplateDef) GetOwnerDefaultsToMember() bool {
	if m != nil {
		return m.OwnerDefaultsToMember
	}
	return false
}

func (m *TemplateDef) GetAdminRefs() []*UserRef {
	if m != nil {
		return m.AdminRefs
	}
	return nil
}

func (m *TemplateDef) GetFieldValues() []*FieldValue {
	if m != nil {
		return m.FieldValues
	}
	return nil
}

func (m *TemplateDef) GetComponentRefs() []*ComponentRef {
	if m != nil {
		return m.ComponentRefs
	}
	return nil
}

func (m *TemplateDef) GetComponentRequired() bool {
	if m != nil {
		return m.ComponentRequired
	}
	return false
}

func (m *TemplateDef) GetApprovalValues() []*Approval {
	if m != nil {
		return m.ApprovalValues
	}
	return nil
}

func (m *TemplateDef) GetPhases() []*PhaseDef {
	if m != nil {
		return m.Phases
	}
	return nil
}

func init() {
	proto.RegisterType((*Project)(nil), "monorail.Project")
	proto.RegisterType((*StatusDef)(nil), "monorail.StatusDef")
	proto.RegisterType((*LabelDef)(nil), "monorail.LabelDef")
	proto.RegisterType((*ComponentDef)(nil), "monorail.ComponentDef")
	proto.RegisterType((*FieldDef)(nil), "monorail.FieldDef")
	proto.RegisterType((*FieldOptions)(nil), "monorail.FieldOptions")
	proto.RegisterType((*ApprovalDef)(nil), "monorail.ApprovalDef")
	proto.RegisterType((*Config)(nil), "monorail.Config")
	proto.RegisterType((*PresentationConfig)(nil), "monorail.PresentationConfig")
	proto.RegisterType((*TemplateDef)(nil), "monorail.TemplateDef")
}

func init() {
	proto.RegisterFile("api/api_proto/project_objects.proto", fileDescriptor_4f680a8ed8804f88)
}

var fileDescriptor_4f680a8ed8804f88 = []byte{
	// 1316 bytes of a gzipped FileDescriptorProto
	0x1f, 0x8b, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0xff, 0x9c, 0x57, 0xdb, 0x6e, 0xdc, 0x36,
	0x13, 0x86, 0xb3, 0xf6, 0xae, 0x76, 0xb4, 0x6b, 0xff, 0xa6, 0x13, 0x43, 0xbf, 0xf1, 0x1f, 0x9c,
	0x4d, 0x8a, 0x1a, 0x01, 0xea, 0xb4, 0x4e, 0xda, 0xf4, 0x80, 0x5e, 0xa4, 0x4e, 0x02, 0x14, 0xad,
	0x63, 0x57, 0x76, 0x8a, 0xe6, 0xa6, 0x04, 0x57, 0x1a, 0xc5, 0x6c, 0x24, 0x51, 0x21, 0x29, 0x27,
	0xfb, 0x12, 0x05, 0x0a, 0xf4, 0x29, 0xfa, 0x34, 0xbd, 0xec, 0x5b, 0xf4, 0x15, 0x0a, 0x8e, 0x28,
	0xef, 0x21, 0x76, 0x92, 0xf6, 0x6a, 0x87, 0x33, 0xdf, 0x1c, 0xc4, 0x21, 0xbf, 0xe1, 0xc2, 0x0d,
	0x51, 0xc9, 0xdb, 0xa2, 0x92, 0xbc, 0xd2, 0xca, 0xaa, 0xdb, 0x95, 0x56, 0x3f, 0x61, 0x62, 0xb9,
	0x1a, 0xbb, 0x1f, 0xb3, 0x4b, 0x5a, 0x16, 0x14, 0xaa, 0x54, 0x5a, 0xc8, 0x7c, 0x6b, 0x6b, 0x1e,
	0x9e, 0xa8, 0xa2, 0x50, 0x65, 0x83, 0xda, 0xba, 0x3e, 0x6f, 0x93, 0xc6, 0xd4, 0x38, 0x1f, 0x68,
	0xf4, 0x14, 0x7a, 0x47, 0x4d, 0x06, 0xc6, 0x60, 0xb9, 0x14, 0x05, 0x46, 0x4b, 0xdb, 0x4b, 0x3b,
	0xfd, 0x98, 0x64, 0x16, 0x41, 0xcf, 0xd4, 0x45, 0x21, 0xf4, 0x24, 0xba, 0x42, 0xea, 0x76, 0xc9,
	0xb6, 0x21, 0x4c, 0xd1, 0x24, 0x5a, 0x56, 0x56, 0xaa, 0x32, 0xea, 0x90, 0x75, 0x56, 0x35, 0xfa,
	0x75, 0x09, 0xfa, 0xc7, 0x56, 0xd8, 0xda, 0x3c, 0xc0, 0x8c, 0x6d, 0x42, 0xd7, 0xd0, 0xc2, 0xc7,
	0xf7, 0x2b, 0xf6, 0x5f, 0x80, 0x02, 0x45, 0x69, 0xb8, 0xaa, 0xb0, 0xa4, 0x24, 0x41, 0xdc, 0x27,
	0xcd, 0x61, 0x85, 0xa5, 0x2b, 0x4a, 0x8b, 0xf2, 0x39, 0xc5, 0x1f, 0xc6, 0x24, 0xb3, 0xff, 0x40,
	0x3f, 0x55, 0x89, 0xb1, 0x5a, 0x96, 0xcf, 0xa2, 0x65, 0x8a, 0x36, 0x55, 0xb0, 0xff, 0x01, 0xa4,
	0x58, 0x69, 0x4c, 0x84, 0xc5, 0x34, 0x5a, 0xa1, 0x80, 0x33, 0x9a, 0xd1, 0x8f, 0x10, 0x7c, 0x2b,
	0xc6, 0x98, 0xbb, 0xa2, 0xae, 0xc2, 0x4a, 0xee, 0x64, 0x5f, 0x53, 0xb3, 0x98, 0x8f, 0xdf, 0x79,
	0x73, 0xfc, 0xe5, 0xd7, 0xe2, 0xff, 0xd2, 0x81, 0xc1, 0xbe, 0x2a, 0x2a, 0x55, 0x62, 0x69, 0x5d,
	0x12, 0x06, 0xcb, 0x95, 0xb0, 0xa7, 0xed, 0xbe, 0x3a, 0x79, 0x3e, 0xc5, 0x95, 0xc5, 0x14, 0x1f,
	0x02, 0x88, 0xb4, 0x90, 0x25, 0xd7, 0x98, 0x99, 0xa8, 0xb3, 0xdd, 0xd9, 0x09, 0xf7, 0xd6, 0x77,
	0xdb, 0x96, 0xef, 0x3e, 0x31, 0xa8, 0x63, 0xcc, 0xe2, 0x3e, 0x81, 0x62, 0xcc, 0x0c, 0xbb, 0x05,
	0xbd, 0x24, 0x69, 0xe0, 0xcb, 0x97, 0xc1, 0xbb, 0x49, 0x42, 0xd8, 0xb7, 0x6c, 0x90, 0xeb, 0x79,
	0xa2, 0x91, 0x8c, 0xdd, 0xed, 0xa5, 0x9d, 0x5e, 0xdc, 0x2e, 0xd9, 0x1e, 0x84, 0x24, 0x2a, 0xed,
	0x52, 0x45, 0xbd, 0xed, 0xa5, 0x8b, 0x33, 0x81, 0x47, 0xc5, 0x98, 0xb1, 0x2d, 0x08, 0x0a, 0x95,
	0xca, 0x4c, 0x62, 0x1a, 0x05, 0x14, 0xee, 0x7c, 0xcd, 0xee, 0xc2, 0xc0, 0xcb, 0x4d, 0xc0, 0xfe,
	0x65, 0x01, 0xc3, 0x16, 0xe6, 0x22, 0x7e, 0x04, 0x40, 0x7d, 0x6a, 0x3e, 0x17, 0xe8, 0x73, 0xd9,
	0xd4, 0x87, 0x9a, 0x4b, 0xdb, 0x93, 0x7b, 0xc9, 0x8c, 0x7e, 0xeb, 0x40, 0xf0, 0x48, 0x62, 0x9e,
	0xba, 0x7e, 0xdc, 0x86, 0x7e, 0xe6, 0x64, 0x4a, 0xb9, 0x44, 0x29, 0x67, 0xdc, 0x09, 0xe6, 0xdc,
	0x83, 0xcc, 0x4b, 0xec, 0x7d, 0x58, 0x13, 0x55, 0x95, 0xcb, 0x44, 0x8c, 0x73, 0xe4, 0x76, 0x52,
	0xa1, 0x6f, 0xd9, 0xea, 0x54, 0x7d, 0x32, 0xa9, 0x90, 0xfd, 0x1f, 0x42, 0x69, 0xb8, 0xc6, 0x17,
	0xb5, 0xd4, 0x98, 0xd2, 0xd1, 0x09, 0x62, 0x90, 0x26, 0xf6, 0x1a, 0xf6, 0x6f, 0x08, 0xa4, 0xe1,
	0xa5, 0x4c, 0x4e, 0xd1, 0x9f, 0x9c, 0x9e, 0x34, 0x8f, 0xdd, 0x92, 0xbd, 0x07, 0xab, 0xd2, 0xf0,
	0xa2, 0xce, 0xad, 0x3c, 0x13, 0x79, 0x7d, 0xde, 0x99, 0xa1, 0x34, 0x07, 0x53, 0xe5, 0xfc, 0xc1,
	0xe9, 0xbe, 0xf9, 0xe0, 0xf4, 0xde, 0xe1, 0xe0, 0xdc, 0xa4, 0xb4, 0xd5, 0xa9, 0x30, 0xc8, 0xe9,
	0x83, 0xa9, 0x49, 0x41, 0x3c, 0x90, 0xe6, 0xc8, 0x29, 0x69, 0x3b, 0x5c, 0xa3, 0x6a, 0x83, 0x9a,
	0x27, 0xa7, 0x4a, 0x26, 0x68, 0xa2, 0xfe, 0x65, 0x91, 0x43, 0x07, 0xdb, 0x6f, 0x50, 0xec, 0x63,
	0x18, 0x60, 0x59, 0x17, 0xe7, 0x5e, 0x17, 0xb7, 0xea, 0x81, 0x73, 0x73, 0x38, 0xef, 0x36, 0x52,
	0x30, 0xa0, 0xac, 0x87, 0x44, 0x23, 0xe6, 0xef, 0xf7, 0x6b, 0x17, 0xfa, 0x54, 0x2d, 0x6d, 0xc2,
	0x95, 0xcb, 0x4a, 0x0d, 0xea, 0x46, 0x30, 0xa3, 0x9f, 0x97, 0x20, 0xbc, 0x5f, 0x55, 0x5a, 0x9d,
	0x89, 0xfc, 0x1f, 0x1d, 0x90, 0x4f, 0x60, 0x28, 0xc8, 0xff, 0xad, 0x49, 0x07, 0x2d, 0x8e, 0x36,
	0xdf, 0x71, 0x62, 0xad, 0xcf, 0x70, 0xe2, 0x59, 0xc6, 0xaf, 0x46, 0x7f, 0x76, 0xa0, 0xbb, 0xaf,
	0xca, 0x4c, 0x3e, 0x63, 0xd7, 0x61, 0xd0, 0x4e, 0x80, 0x19, 0x72, 0x0e, 0xbd, 0xee, 0xb1, 0xe3,
	0xe8, 0xbb, 0x10, 0x36, 0x5c, 0xca, 0xd3, 0x69, 0xee, 0x8d, 0x69, 0xee, 0x73, 0x0e, 0x8e, 0xc1,
	0xb4, 0xa2, 0x61, 0x0f, 0xe1, 0x6a, 0xb3, 0x42, 0xc3, 0x55, 0x96, 0xa1, 0xe6, 0x05, 0xea, 0x67,
	0xe8, 0xd9, 0xe6, 0x35, 0x77, 0x57, 0x3c, 0x6b, 0x1d, 0x0e, 0x1d, 0xfe, 0xc0, 0xc1, 0xa7, 0x97,
	0x31, 0x9d, 0x72, 0xcf, 0x45, 0x1d, 0x6e, 0x2e, 0x23, 0x65, 0xfe, 0x14, 0x22, 0x7c, 0x95, 0xe4,
	0xb5, 0x91, 0x67, 0xc8, 0x1b, 0xe7, 0x4a, 0x63, 0x26, 0x5f, 0xa1, 0x89, 0x56, 0xb6, 0x3b, 0x3b,
	0xfd, 0x78, 0xf3, 0xdc, 0x4e, 0xfe, 0x47, 0xde, 0xca, 0xbe, 0x84, 0xd5, 0xa4, 0x65, 0xd6, 0x26,
	0x61, 0x97, 0x12, 0x6e, 0x4e, 0x13, 0xce, 0x32, 0x6f, 0x3c, 0x4c, 0x66, 0x56, 0xc6, 0xd5, 0xda,
	0xf4, 0x35, 0x9d, 0xde, 0x8e, 0xc5, 0xc6, 0x52, 0xad, 0x99, 0x97, 0x0c, 0xfb, 0xbc, 0xed, 0xac,
	0xf0, 0x5f, 0x18, 0x90, 0xd7, 0xb5, 0xa9, 0xd7, 0xcc, 0xc1, 0x69, 0xbb, 0x2b, 0x9a, 0xef, 0xbc,
	0x05, 0xeb, 0x1a, 0xdd, 0xc5, 0x4c, 0x2c, 0xb7, 0x8a, 0x3f, 0x2f, 0xd5, 0xcb, 0x92, 0x28, 0x2e,
	0x88, 0xd7, 0x5a, 0xc3, 0x89, 0xfa, 0xc6, 0xa9, 0x47, 0x7f, 0x74, 0x80, 0x1d, 0x69, 0x34, 0x58,
	0x5a, 0xe1, 0x4e, 0xbd, 0xef, 0xfe, 0x1e, 0x5c, 0x6b, 0xbb, 0x6f, 0x4f, 0xeb, 0x62, 0x5c, 0x0a,
	0x99, 0xf3, 0x5a, 0xb7, 0xf3, 0x6a, 0xc3, 0x1b, 0x4f, 0x5a, 0xdb, 0x13, 0x9d, 0x3b, 0xb6, 0x6a,
	0x7d, 0xe6, 0x47, 0xf7, 0xaa, 0x57, 0x1f, 0xfb, 0x09, 0x7e, 0x07, 0x36, 0x93, 0xda, 0x58, 0x55,
	0xf0, 0xe6, 0x61, 0x80, 0xa5, 0xd5, 0x13, 0x8a, 0xde, 0x9c, 0xc6, 0x8d, 0xc6, 0xfa, 0xb5, 0x33,
	0x3e, 0x74, 0x36, 0x17, 0xfd, 0x06, 0x0c, 0x53, 0xcc, 0x44, 0x9d, 0x5b, 0xfe, 0xa2, 0x46, 0x3d,
	0xf1, 0xf3, 0x77, 0xe0, 0x95, 0xdf, 0x39, 0x1d, 0xfb, 0x0c, 0x86, 0x46, 0x9c, 0x61, 0x4a, 0x10,
	0xe9, 0xdb, 0x1a, 0xee, 0x5d, 0x9d, 0x39, 0x54, 0xce, 0x4c, 0xe0, 0x78, 0x60, 0x5a, 0x59, 0xa2,
	0x61, 0xbb, 0xb0, 0xa1, 0xf1, 0x4c, 0x1a, 0xa9, 0x4a, 0x57, 0x0a, 0xcf, 0x94, 0x2e, 0x84, 0xf5,
	0x4c, 0xb7, 0xde, 0x9a, 0x9e, 0xe8, 0xfc, 0x11, 0x19, 0xd8, 0x0e, 0xfc, 0xab, 0xad, 0x27, 0x51,
	0x39, 0x37, 0x15, 0x26, 0x34, 0x97, 0xfa, 0xf1, 0xaa, 0xd7, 0xef, 0xab, 0xfc, 0xb8, 0xc2, 0xc4,
	0xb5, 0xa3, 0x45, 0x1a, 0xa5, 0x6d, 0x03, 0x0d, 0x08, 0xba, 0xe6, 0x0d, 0xc7, 0x4a, 0x5b, 0xc2,
	0xde, 0x84, 0xd6, 0x9b, 0xbf, 0xe2, 0xc2, 0x5a, 0x4d, 0x7d, 0x9b, 0x7e, 0xe6, 0x0f, 0xf7, 0xad,
	0xd5, 0xb3, 0xa8, 0x49, 0x83, 0x82, 0x39, 0xd4, 0x53, 0x87, 0x1a, 0xfd, 0xbe, 0x02, 0xe1, 0x09,
	0x16, 0x55, 0x2e, 0x2c, 0x3a, 0x76, 0xb9, 0x01, 0x43, 0xeb, 0x97, 0xb3, 0x57, 0x7a, 0xd0, 0x2a,
	0x1f, 0xfb, 0x77, 0x57, 0xa2, 0x4a, 0x8b, 0xa5, 0x6d, 0xdf, 0x5d, 0x7e, 0x39, 0xfb, 0x22, 0xeb,
	0xcc, 0xbf, 0xc8, 0xee, 0xc0, 0xa6, 0x17, 0x79, 0x51, 0x1b, 0xcb, 0xc7, 0xc8, 0x31, 0x95, 0xd3,
	0x47, 0xca, 0x86, 0xb7, 0x1e, 0xd4, 0xc6, 0x7e, 0x85, 0x0f, 0xc9, 0xe4, 0xb8, 0x52, 0xbd, 0x2c,
	0xfd, 0xfc, 0x5d, 0xb9, 0x6c, 0xfe, 0x06, 0x84, 0x71, 0x54, 0xb7, 0x07, 0x9e, 0x44, 0xc8, 0xa1,
	0x4b, 0x0e, 0x17, 0x92, 0x45, 0xdf, 0xb4, 0xe2, 0xc2, 0xc0, 0xee, 0xbd, 0xc3, 0xc0, 0x76, 0xb4,
	0x57, 0x60, 0x31, 0x46, 0x6d, 0xb8, 0x2a, 0xf3, 0x89, 0x1f, 0x4a, 0xa1, 0xd7, 0x1d, 0x96, 0xf9,
	0x84, 0xdd, 0x83, 0xa8, 0xa9, 0xdc, 0xef, 0xb6, 0x71, 0x97, 0xac, 0x01, 0xf8, 0x5b, 0x76, 0x8d,
	0xec, 0x0f, 0xbc, 0xf9, 0x44, 0x1d, 0x90, 0x71, 0x61, 0x48, 0xc2, 0x3b, 0x0c, 0xc9, 0x7b, 0x30,
	0x68, 0x88, 0x83, 0x86, 0xb0, 0x89, 0xc2, 0xc5, 0xe3, 0x4c, 0xd4, 0xf1, 0xbd, 0x33, 0xc6, 0x61,
	0x76, 0x2e, 0x2f, 0x10, 0x16, 0xa5, 0x1b, 0x5c, 0x4a, 0x58, 0xf1, 0x1c, 0x61, 0x51, 0xde, 0x0f,
	0x80, 0xcd, 0xba, 0xfb, 0x67, 0xc5, 0x90, 0x3e, 0x6e, 0x7d, 0x06, 0xea, 0x5f, 0x17, 0x5f, 0xd0,
	0x3b, 0xa5, 0x21, 0x2b, 0x5f, 0xe9, 0xea, 0xe2, 0x66, 0xb7, 0x74, 0x45, 0x6f, 0x17, 0x92, 0x7c,
	0xa9, 0xb7, 0xa0, 0x4b, 0xaf, 0x00, 0x13, 0xad, 0x2d, 0xfa, 0xd0, 0x43, 0xc0, 0xf1, 0x9b, 0x47,
	0x8c, 0xbb, 0xf4, 0xdf, 0xe1, 0xce, 0x5f, 0x01, 0x00, 0x00, 0xff, 0xff, 0x93, 0x9a, 0x55, 0x90,
	0xab, 0x0c, 0x00, 0x00,
}
