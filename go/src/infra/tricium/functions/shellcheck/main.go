package main

import (
	"flag"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	tricium "infra/tricium/api/v1"
	"infra/tricium/functions/shellcheck/runner"
)

const (
	analyzerName   = "ShellCheck"
	bundledBinPath = "bin/shellcheck/shellcheck"
)

var (
	runnerLogger = log.New(os.Stderr, "shellcheck", log.LstdFlags)
)

func main() {
	inputDir := flag.String("input", "", "Path to root of Tricium input")
	outputDir := flag.String("output", "", "Path to root of Tricium output")
	shellCheckPath := flag.String("shellcheck_path", "", "Path to shellcheck binary")

	exclude := flag.String("exclude", "", "Exclude warnings (see shellcheck")
	shell := flag.String("shell", "", "Specify dialect (see shellcheck")
	enable := flag.String("enable", "", "Enable optional checks (see shellcheck)")

	// This is needed until/unless crbug.com/863106 is fixed.
	pathFilters := flag.String("path_filters", "", "Patterns to filter file list")

	flag.Parse()
	if flag.NArg() != 0 {
		log.Panicf("Unexpected argument")
	}

	r := &runner.Runner{
		Path:    *shellCheckPath,
		Dir:     *inputDir,
		Exclude: *exclude,
		Enable:  *enable,
		Shell:   *shell,
		Logger:  runnerLogger,
	}

	if r.Path == "" {
		// No explicit shellcheck_bin; try to find one.
		r.Path = findShellCheckBin()
		if r.Path == "" {
			log.Panic("Couldn't find shellcheck bin!")
		}
		// Validate that the found binary is a supported version of shellcheck.
		version, err := r.Version()
		if err != nil {
			log.Panicf("Error checking shellcheck version: %v", err)
		}
		if !strings.HasPrefix(version, "0.") || version < "0.6" {
			log.Panicf("Found shellcheck with unsupported version %q", version)
		}
	}

	run(r, *inputDir, *outputDir, *pathFilters)
}

func run(r *runner.Runner, inputDir, outputDir, pathFilters string) {
	// Read Tricium input FILES data.
	input := &tricium.Data_Files{}
	if err := tricium.ReadDataType(inputDir, input); err != nil {
		log.Panicf("Failed to read FILES data: %v", err)
	}
	log.Printf("Read FILES data.")

	filtered, err := tricium.FilterFiles(input.Files, strings.Split(pathFilters, ",")...)
	if err != nil {
		log.Panicf("Failed to filter files: %v", err)
	}

	// Run shellcheck on input files.
	paths := make([]string, len(filtered))
	for i, f := range filtered {
		paths[i] = f.Path
	}

	var warns []runner.Warning
	if len(paths) > 0 {
		warns, err = r.Warnings(paths...)
		if err != nil {
			log.Panicf("Error running shellcheck: %v", err)
		}
	} else {
		log.Printf("No files to check.")
	}

	// Convert shellcheck warnings into Tricium results.
	results := &tricium.Data_Results{}
	for _, warn := range warns {
		results.Comments = append(results.Comments, &tricium.Data_Comment{
			// e.g. "ShellCheck/SC1234"
			Category: fmt.Sprintf("%s/SC%d", analyzerName, warn.Code),
			Message:  fmt.Sprintf("%s: %s\n\n%s", warn.Level, warn.Message, warn.WikiURL()),
			Path:     warn.File,
			// shellcheck uses 1-based columns, but Tricium needs 0-based columns.
			StartLine: warn.Line,
			EndLine:   warn.EndLine,
			StartChar: warn.Column - 1,
			EndChar:   warn.EndColumn - 1,
		})
	}

	// Write Tricium RESULTS data.
	path, err := tricium.WriteDataType(outputDir, results)
	if err != nil {
		log.Panicf("Failed to write RESULTS data: %v", err)
	}
	log.Printf("Wrote RESULTS data to path %q.", path)
}

func findShellCheckBin() string {
	// Look for bundled shellcheck next to this executable.
	ex, err := os.Executable()
	if err == nil {
		bundledPath := filepath.Join(filepath.Dir(ex), bundledBinPath)
		if path, err := exec.LookPath(bundledPath); err == nil {
			return path
		}
	}
	// Look in PATH.
	if path, err := exec.LookPath("shellcheck"); err == nil {
		return path
	}
	return ""
}
