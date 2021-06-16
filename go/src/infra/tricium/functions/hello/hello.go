// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the Hello analyzer.
package main

import (
	"flag"
	"log"

	"infra/tricium/api/v1"
)

const (
	category = "Hello"
	message  = "Hello"
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	flag.Parse()
	if flag.NArg() != 0 {
		log.Panicf("Unexpected argument")
	}

	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(*inputDir, input); err != nil {
		log.Panicf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data: %+v", input)

	// Create RESULTS data.
	output := &tricium.Data_Results{}
	for _, file := range input.Files {
		if file.IsBinary {
			log.Printf("Not performing Hello checks on binary file: %s", file.Path)
			continue
		}
		output.Comments = append(output.Comments, &tricium.Data_Comment{
			Category: category,
			Message:  message,
			Path:     file.Path,
		})
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(*outputDir, output)
	if err != nil {
		log.Panicf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data, path: %q, value: %v\n", path, output)
}
