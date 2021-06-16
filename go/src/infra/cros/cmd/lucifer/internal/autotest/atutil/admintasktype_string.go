// Code generated by "stringer -type=AdminTaskType"; DO NOT EDIT.

package atutil

import "strconv"

func _() {
	// An "invalid array index" compiler error signifies that the constant values have changed.
	// Re-run the stringer command to generate them again.
	var x [1]struct{}
	_ = x[NoTask-0]
	_ = x[Verify-1]
	_ = x[Cleanup-2]
	_ = x[Reset-3]
	_ = x[Repair-4]
}

const _AdminTaskType_name = "NoTaskVerifyCleanupResetRepair"

var _AdminTaskType_index = [...]uint8{0, 6, 12, 19, 24, 30}

func (i AdminTaskType) String() string {
	if i < 0 || i >= AdminTaskType(len(_AdminTaskType_index)-1) {
		return "AdminTaskType(" + strconv.FormatInt(int64(i), 10) + ")"
	}
	return _AdminTaskType_name[_AdminTaskType_index[i]:_AdminTaskType_index[i+1]]
}