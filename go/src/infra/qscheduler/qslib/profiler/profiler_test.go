// Copyright 2019 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package profiler

import (
	"bytes"
	"compress/zlib"
	"fmt"
	"testing"

	"github.com/golang/protobuf/proto"
)

var params = StateParams{
	LabelCorpusSize:     1000,
	ProvisionableLabels: 20,

	LabelsPerWorker: 50,
	Workers:         5000,

	LabelsPerTask: 5,
	Tasks:         100000,

	Accounts: 20,
}

// BenchmarkEntitySize prints the typical proto-serialized size
// of a scheduler, and benchmarks its serialization time.
func BenchmarkEntitySize(b *testing.B) {
	state := NewSchedulerState(params)

	b.ResetTimer()

	var protoBytes []byte
	for i := 0; i < b.N; i++ {
		stateProto := state.ToProto()
		protoBytes, _ = proto.Marshal(stateProto)
	}

	fmt.Printf("proto size: %.1f MiB\n", float64(len(protoBytes))/1024.0/1024.0)
}

func BenchmarkEntityZip(b *testing.B) {
	state := NewSchedulerState(params)

	stateProto := state.ToProto()
	protoBytes, _ := proto.Marshal(stateProto)

	b.ResetTimer()

	var compressedBytes []byte
	for i := 0; i < b.N; i++ {
		buffer := &bytes.Buffer{}
		w := zlib.NewWriter(buffer)
		w.Write(protoBytes)
		w.Close()
		compressedBytes = buffer.Bytes()
	}

	fmt.Printf("compressed proto size: %.1f MiB\n", float64(len(compressedBytes))/1024.0/1024.0)
}

func BenchmarkSchedulerSimulation(b *testing.B) {
	// These parameters are chosen to try to mimick expected scaling limits.
	// By the end of this simulation:
	// - There are 5k workers.
	// - There are 100k tasks.
	// - If DisableFreeTasks were false, about 2.2k of the workers would be
	//   running, and the others are idle.
	// - With DisableFreeTasks set to true, only about 1.5k are running. This
	// - is due to a combination of the limited maximum charge rate and the
	//   fanout limit.
	params := SimulationParams{
		Iterations: 100,
		StateParams: StateParams{
			LabelCorpusSize:     1000,
			ProvisionableLabels: 50,

			LabelsPerWorker: 50,
			LabelsPerTask:   4,

			Tasks:   1000,
			Workers: 50,

			Accounts:         20,
			ChargeRateMax:    10,
			ChargeTime:       10,
			DisableFreeTasks: true,
			Fanout:           2,
		},
	}
	for i := 0; i < b.N; i++ {
		RunSimulation(params)
	}
}
