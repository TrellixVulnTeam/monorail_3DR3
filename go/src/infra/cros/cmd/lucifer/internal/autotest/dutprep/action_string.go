// Code generated by "stringer -type=Action"; DO NOT EDIT.

package dutprep

import "strconv"

func _() {
	// An "invalid array index" compiler error signifies that the constant values have changed.
	// Re-run the stringer command to generate them again.
	var x [1]struct{}
	_ = x[NoAction-0]
	_ = x[StageUSB-1]
	_ = x[InstallTestImage-2]
	_ = x[InstallFirmware-3]
	_ = x[RunPreDeployVerification-4]
	_ = x[VerifyRecoveryMode-5]
	_ = x[SetupLabstation-6]
	_ = x[UpdateLabel-7]
}

const _Action_name = "NoActionStageUSBInstallTestImageInstallFirmwareRunPreDeployVerificationVerifyRecoveryModeSetupLabstationUpdateLabel"

var _Action_index = [...]uint8{0, 8, 16, 32, 47, 71, 89, 104, 115}

func (i Action) String() string {
	if i < 0 || i >= Action(len(_Action_index)-1) {
		return "Action(" + strconv.FormatInt(int64(i), 10) + ")"
	}
	return _Action_name[_Action_index[i]:_Action_index[i+1]]
}
