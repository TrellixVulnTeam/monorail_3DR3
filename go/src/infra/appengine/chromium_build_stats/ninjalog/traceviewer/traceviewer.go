// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

/*
Package traceviewer generates trace-viewer page from *ninjalog.NinjaLog.

*/
package traceviewer

import (
	"bufio"
	"bytes"
	"compress/gzip"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"html/template"
	"os"
	"strings"

	"infra/appengine/chromium_build_stats/ninjalog"
)

// TODO(ukai): use html/template as template.
// it won't work, even if we use delims such as "{{||" and "||}}".

// Template is a trace-viewer template.
type Template struct {
	fname string
}

// Parse parses trace-viewer template file, generated by
// ../../../gen-trace-viewer.sh.
func Parse(fname string) (*Template, error) {
	return &Template{
		fname: fname,
	}, nil
}

// Must is a helper that wraps a call to Parse() and panics if the error is non-nil.
// It is intended for use in variable initializations.
func Must(t *Template, err error) *Template {
	if err != nil {
		panic(err)
	}
	return t
}

// HTML generates html pages to render ninjalog's trace view.
func (t *Template) HTML(fname string, traces []ninjalog.Trace) ([]byte, error) {
	js, err := json.Marshal(traces)
	if err != nil {
		return nil, err
	}

	var buf bytes.Buffer
	bw := base64.NewEncoder(base64.StdEncoding, &buf)
	gz := gzip.NewWriter(bw)
	_, err = gz.Write(js)
	if err != nil {
		gz.Close()
		return nil, err
	}
	err = gz.Close()
	if err != nil {
		return nil, err
	}

	f, err := os.Open(t.fname)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var w bytes.Buffer
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if line == `<script id="viewer-data" type="text/plain">` {
			fmt.Fprintf(&w, "%s\n", line)
			break
		}
		if strings.HasPrefix(line, `  <title>Trace from`) {
			fmt.Fprintf(&w, "  <title>Trace from %s</title>\n", template.HTMLEscapeString(fname))
			continue
		}
		fmt.Fprintf(&w, "%s\n", line)
	}
	fmt.Fprintf(&w, "%s\n", buf.String())
	for scanner.Scan() {
		line := scanner.Text()
		if line == `</script>` {
			fmt.Fprintf(&w, "%s\n", line)
			break
		}
	}
	for scanner.Scan() {
		fmt.Fprintf(&w, "%s\n", scanner.Text())
	}
	if err = scanner.Err(); err != nil {
		return nil, err
	}
	return w.Bytes(), err
}
