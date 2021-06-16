package handlers

import (
	"context"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/luci/server/auth"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"infra/appengine/rotang"

	apb "infra/appengine/rotang/proto/rotangapi"
)

// MakeAllMembersOwners sets all rotation members as owners.
func (h *State) MakeAllMembersOwners(ctx context.Context, req *apb.MakeAllMembersOwnersRequest) (*apb.MakeAllMembersOwnersResponse, error) {
	if req.GetName() == "" {
		return nil, status.Errorf(codes.InvalidArgument, "rotation name is required")
	}

	cfgs, err := h.configStore(ctx).RotaConfig(ctx, req.GetName())
	if err != nil {
		return nil, err
	}

	if len(cfgs) != 1 {
		return nil, status.Errorf(codes.Internal, "RotaConfig did not return 1 configuration, got: %d", len(cfgs))
	}

	cfg := cfgs[0]

	if !isOwner(ctx, cfg) {
		return nil, status.Errorf(codes.PermissionDenied, "not an owner of rotation: %q", req.GetName())
	}

	if len(cfg.Members) < 1 {
		return &apb.MakeAllMembersOwnersResponse{}, nil
	}

	usr := auth.CurrentUser(ctx)
	if usr == nil || usr.Email == "" {
		return nil, status.Errorf(codes.InvalidArgument, "current user not set")
	}

	// Make sure the current user is still in the list.
	syncedOwners := []string{usr.Email}
	for _, shiftMember := range cfg.Members {
		if shiftMember.Email == usr.Email {
			continue
		}
		syncedOwners = append(syncedOwners, shiftMember.Email)
	}
	cfg.Config.Owners = syncedOwners

	if err := h.configStore(ctx).UpdateRotaConfig(ctx, cfg); err != nil {
		return nil, err
	}

	return &apb.MakeAllMembersOwnersResponse{}, nil
}

// RotationMembers return information for all members of a rotation.
func (h *State) RotationMembers(ctx context.Context, req *apb.RotationMembersRequest) (*apb.RotationMembersResponse, error) {
	if req.GetName() == "" {
		return nil, status.Errorf(codes.InvalidArgument, "rotation name is required")
	}

	cfg, err := h.configStore(ctx).RotaConfig(ctx, req.Name)
	if err != nil {
		return nil, err
	}

	if len(cfg) != 1 {
		return nil, status.Errorf(codes.Internal, "RotaConfig did not return 1 configuration, got: %d", len(cfg))
	}

	shifts, err := h.shiftStore(ctx).AllShifts(ctx, req.Name)
	if err != nil && status.Code(err) != codes.NotFound {
		return nil, err
	}

	shiftMap := make(map[string][]rotang.ShiftEntry)
	for _, shift := range shifts {
		for _, o := range shift.OnCall {
			shiftMap[o.Email] = append(shiftMap[o.Email], shift)
		}
	}

	memberInfo, err := h.protoMember(ctx, cfg[0].Members)
	if err != nil && status.Code(err) != codes.NotFound {
		return nil, err
	}

	for _, m := range memberInfo {
		ss, ok := shiftMap[m.Member.Email]
		if !ok {
			continue
		}
		ssProto, err := h.shiftsToProto(ctx, ss)
		if err != nil {
			return nil, err
		}
		m.OncallShifts = ssProto
	}

	return &apb.RotationMembersResponse{
		Rotation: req.GetName(),
		Members:  memberInfo,
	}, nil
}

func (h *State) protoMember(ctx context.Context, shiftMembers []rotang.ShiftMember) ([]*apb.MemberInfo, error) {
	var res []*apb.MemberInfo
	memberStore := h.memberStore(ctx)
	for _, sm := range shiftMembers {
		member, err := memberStore.Member(ctx, sm.Email)
		if err != nil {
			return nil, err
		}

		var protoOOO []*apb.OOO
		for _, ooo := range member.OOO {
			protoStart, err := ptypes.TimestampProto(ooo.Start)
			if err != nil {
				return nil, err
			}
			protoEnd, err := ptypes.TimestampProto(ooo.Start.Add(ooo.Duration))
			if err != nil {
				return nil, err
			}
			protoOOO = append(protoOOO, &apb.OOO{
				Start:   protoStart,
				End:     protoEnd,
				Comment: ooo.Comment,
			})
		}

		res = append(res, &apb.MemberInfo{
			Member: &apb.OnCaller{
				Email: member.Email,
				Name:  member.Name,
				Tz:    member.TZ.String(),
			},
			Ooo: protoOOO,
		})
	}
	return res, nil
}
