package testexpectations

import (
	"encoding/json"
	"fmt"
	"sort"
	"strings"

	"golang.org/x/net/context"

	"infra/appengine/sheriff-o-matic/som/client"
)

const (
	defaultExpectationsFile = "third_party/blink/web_tests/TestExpectations"
)

var (
	// LayoutTestExpectations is a map of expectation file locations, relative to repo+branch.
	LayoutTestExpectations = map[string]string{
		"TestExpectations":      "third_party/blink/web_tests/TestExpectations",      // The main test failure suppression file. In theory, this should be used for flaky lines and NeedsRebaseline/NeedsManualRebaseline lines.
		"ASANExpectations":      "third_party/blink/web_tests/ASANExpectations",      // Tests that fail under ASAN.
		"LeakExpectations":      "third_party/blink/web_tests/LeakExpectations",      // Tests that have memory leaks under the leak checker.
		"MSANExpectations":      "third_party/blink/web_tests/MSANExpectations",      // Tests that fail under MSAN.
		"NeverFixTests":         "third_party/blink/web_tests/NeverFixTests",         // Tests that we never intend to fix (e.g. a test for Windows-specific behavior will never be fixed on Linux/Mac). Tests that will never pass on any platform should just be deleted, though.
		"SlowTests":             "third_party/blink/web_tests/SlowTests",             // Tests that take longer than the usual timeout to run. Slow tests are given 5x the usual timeout.
		"SmokeTests":            "third_party/blink/web_tests/SmokeTests",            // A small subset of tests that we run on the Android bot.
		"StaleTestExpectations": "third_party/blink/web_tests/StaleTestExpectations", // Platform-specific lines that have been in TestExpectations for many months. They‘re moved here to get them out of the way of people doing rebaselines since they’re clearly not getting fixed anytime soon.
		"W3CImportExpectations": "third_party/blink/web_tests/W3CImportExpectations", // A record of which W3C tests should be imported or skipped.
	}
)

// BuilderConfig represents the expectation settings for a builder.
type BuilderConfig struct {
	// PortName is the name of the OS port.
	PortName string `json:"port_name"`
	// Specifiers modify the conditions of the expectations.
	Specifiers []string `json:"specifiers"`
	// IsTryBuilder is true if the builder is a trybot.
	IsTryBuilder bool `json:"is_try_builder"`
}

const builderConfigFile = "third_party/blink/tools/blinkpy/common/config/builders.json"

// LoadBuilderConfigs loads bulders.json from gitiles.
func LoadBuilderConfigs(c context.Context) (map[string]*BuilderConfig, error) {
	ret := map[string]*BuilderConfig{}
	URL := fmt.Sprintf("https://chromium.googlesource.com/chromium/src/+/master/%s?format=TEXT", builderConfigFile)
	b, err := client.GetGitilesCached(c, URL)
	if err != nil {
		return nil, err
	}

	if err := json.Unmarshal(b, &ret); err != nil {
		return nil, err
	}

	return ret, nil
}

// FileSet is a set of expectation files.
type FileSet struct {
	Files []*File
}

// File is an expectation file.
type File struct {
	Path         string
	Expectations []*ExpectationStatement
}

func (f *File) String() string {
	s := []string{}
	for _, e := range f.Expectations {
		s = append(s, e.String())
	}
	return strings.Join(s, "\n")
}

// LoadAll returns a FileSet of all known layout test expectation files.
func LoadAll(c context.Context) (*FileSet, error) {
	type resp struct {
		err  error
		file *File
	}

	rCh := make(chan resp)

	for n, p := range LayoutTestExpectations {
		name, path := n, p
		go func() {
			r := resp{}

			// TODO: get blamelist for authors of each line too.
			URL := fmt.Sprintf("https://chromium.googlesource.com/chromium/src/+/master/%s?format=TEXT", path)
			b, err := client.GetGitilesCached(c, URL)
			if err != nil {
				r.err = fmt.Errorf("error reading: %s", err)
				rCh <- r
				return
			}
			lines := strings.Split(string(b), "\n")
			stmts := make([]*ExpectationStatement, len(lines))
			for n, line := range lines {
				p := NewStringParser(line)
				stmt, err := p.Parse()
				if err != nil {
					r.err = fmt.Errorf("error parsing %s:%d %q: %s", name, n, line, err)
					rCh <- r
					return
				}
				stmt.LineNumber = n
				stmts[n] = stmt
			}
			r.file = &File{Path: path, Expectations: stmts}
			rCh <- r
			return
		}()
	}

	ret := &FileSet{}
	errs := []error{}

	for range LayoutTestExpectations {
		r := <-rCh
		if r.err != nil {
			errs = append(errs, r.err)
		} else {
			ret.Files = append(ret.Files, r.file)
		}
	}

	if len(errs) > 0 {
		return nil, fmt.Errorf("errors fetching Expectation files: %v", errs)
	}
	return ret, nil
}

// UpdateExpectation updates a test expectation within a FileSet.
func (fs *FileSet) UpdateExpectation(es *ExpectationStatement) error {
	// Find all files that mention es.TestName already
	// Naive: just replace any existing rules. This won't work in practice.
	for _, file := range fs.Files {
		for _, exp := range file.Expectations {
			// TODO: deal with directories in addition to exact matches.
			if exp.TestName == es.TestName {
				exp.Expectations = es.Expectations
				exp.Modifiers = es.Modifiers
				exp.Bugs = es.Bugs
				exp.Dirty = true
				return nil
			}
		}
	}

	// Add a new expectation line to one of the test expectation files since
	// we didn't find a matching line in any of the existing files.
	for _, file := range fs.Files {
		// By default, use the default TestExpectations file.
		if file.Path == defaultExpectationsFile {
			es.LineNumber = 0 // be smarter about picking this.
			es.Dirty = true
			file.Expectations = append(file.Expectations, es)
			return nil
		}
	}

	return fmt.Errorf("could not find a place to add this change: %+v", *es)
}

type byOverrides []*ExpectationStatement

func (l byOverrides) Len() int           { return len(l) }
func (l byOverrides) Less(i, j int) bool { return l[i].Overrides(l[j]) }
func (l byOverrides) Swap(i, j int)      { l[i], l[j] = l[j], l[i] }

// ToCL returns a map of file paths to new file contents.
func (fs *FileSet) ToCL() map[string]string {
	// TODO: expectation coalescing, normalizing, splitting. This is probably
	// not the right function to implement those operations but they need to be
	// implemented.
	ret := map[string]string{}
	for _, file := range fs.Files {
		for _, s := range file.Expectations {
			// Only include files with modified lines in the CL.
			if s.Dirty {
				ret[file.Path] = file.String()
			}
		}
	}
	return ret
}

// NameMatch returns true if the extatement matches testName.
func (es *ExpectationStatement) NameMatch(testName string) bool {
	// Comment and blank lines have no test name.
	if es.TestName == "" {
		return false
	}

	// Direct matches.
	if testName == es.TestName {
		return true
	}

	// Partial matches.
	if es.IsDir() && strings.HasPrefix(testName, es.TestName) {
		return true
	}

	return false
}

// IsDir returns true if the statement's test name is actually a file path to
// a directory rather than an individual test.
func (es *ExpectationStatement) IsDir() bool {
	// If the expectation specifies a file path that is a directory, it
	// applies to anything under that directory. This "doesn't end in .html"
	// heuristic may be too brittle. TODO: Investigate accuracy of this assumption,
	// and look into alternatives if it doesn't hold.
	// In particular, look into virtual_test_suites in
	// third_party/WebKit/Tools/Scripts/webkitpy/layout_tests/port/base.py

	return !strings.HasSuffix(es.TestName, ".html")
}

// ExpandModifiers returns the list of all modifiers that the rule should match.
func (es *ExpectationStatement) ExpandModifiers() []string {
	ret := es.Modifiers
	for _, m := range es.Modifiers {
		switch strings.ToLower(m) {
		case "mac":
			ret = append(ret, "retina", "mac10.9", "mac10.11", "mac10.12")
			break
		case "win":
			ret = append(ret, "win7", "win10")
			break
		case "linux":
			ret = append(ret, "trusty")
			break
		case "android":
			ret = append(ret, "kitkat")
		}
	}

	return ret
}

// ModifierMatch returns true if the given modifier matches the statement's
// modifier or any of its expanded modifiers.
func (es *ExpectationStatement) ModifierMatch(mod string) bool {
	if len(es.Modifiers) == 0 {
		// No modifers specified means it applies to all configurations.
		return true
	}

	for _, m := range es.ExpandModifiers() {
		if strings.ToLower(m) == strings.ToLower(mod) {
			return true
		}
	}
	return false
}

// Overrides returns true if the receiver should override other when evaluating
// statement matches for a given test, configuration. This establishes an
// ordering on the expectation statements so they can be sorted by precedence.
func (es *ExpectationStatement) Overrides(other *ExpectationStatement) bool {
	// Similarly to CSS selectors, these rules give preference to higher specificity.
	// First check modifier specificity, then test path specificity.
	// See https://chromium.googlesource.com/chromium/src/+/master/docs/testing/layout_test_expectations.md
	// for more complete documentation.
	if len(other.Modifiers) == 0 && len(es.Modifiers) > 0 {
		// Using any modifiers is more specific than not using any modifiers.
		return true
	}

	if len(other.ExpandModifiers()) > len(other.Modifiers) &&
		len(es.ExpandModifiers()) == len(es.Modifiers) &&
		len(es.Modifiers) > 0 {
		// other is using a modifier macro, which is less specific than a particular configuration.
		return true
	}

	if other.IsDir() && !es.IsDir() {
		// other is using a directory path, which is less specific than a particluar test file name.
		return true
	}

	return false
}

// Applies returns true if the statement applies to the given test, configuration.
func (es *ExpectationStatement) Applies(testName, configuration string) bool {
	return es.NameMatch(testName) && es.ModifierMatch(configuration)
}

// ForTest returns a list of ExpectationStatement, sorted in decreasing order of
// precedence, that match the given test and configuration.
func (fs *FileSet) ForTest(testName string, config *BuilderConfig) []*ExpectationStatement {
	ret := []*ExpectationStatement{}
	for _, file := range fs.Files {
		for _, s := range file.Expectations {
			// If the statement does not include modifiers, it applies to any test config
			// that matches the test name.
			if len(s.Modifiers) == 0 && s.Applies(testName, "") {
				ret = append(ret, s)
			}

			// Now check if the expectation matches *all* of the test configuration specifiers.
			specMatch := true
			for _, spec := range config.Specifiers {
				specMatch = specMatch && s.Applies(testName, spec)
			}
			if specMatch && len(s.Modifiers) > 0 && len(config.Specifiers) > 0 {
				ret = append(ret, s)
			}
		}
	}

	// Return most specific applicable statement first.
	sort.Sort(byOverrides(ret))
	return ret
}
