// Copyright 2014 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

// compiler_proxy_log.go provides /compiler_proxy_log endpoints.

import (
	"bytes"
	"compress/gzip"
	"context"
	"fmt"
	"html/template"
	"net/http"
	"path"
	"sort"
	"strings"
	"time"

	"cloud.google.com/go/storage"
	"google.golang.org/appengine"
	"google.golang.org/appengine/log"
	"google.golang.org/appengine/user"

	"infra/appengine/chromium_build_stats/compilerproxylog"
	"infra/appengine/chromium_build_stats/logstore"
)

var (
	compilerProxyLogIndexTempl = template.Must(template.New("compiler_proxy_index").Parse(`
<html>
<head>
 <title>{{.Path}}</title>
</head>
<body>
<h1><a href="/file/{{.Path}}">{{.Path}}</a></h1>
<table>
<tr><th>Filename <td>{{.CompilerProxyLog.Filename}}
<tr><th>Created <td>{{.CompilerProxyLog.Created}}
<tr><th>Machine <td>{{.CompilerProxyLog.Machine}}
<tr><th>GomaRevision <td>{{.CompilerProxyLog.GomaRevision}}
<tr><th>GomaVersion <td>{{.CompilerProxyLog.GomaVersion}}
<tr><th>CompilerProxyID prefix<td>{{.CompilerProxyLog.CompilerProxyIDPrefix}}
<tr><th>BuildIDs<td>{{.CompilerProxyLog.BuildIDs}}
<tr><th>GomaFlags <td><pre>{{.CompilerProxyLog.GomaFlags}}</pre>
<tr><th>GomaLimits <td>{{.CompilerProxyLog.GomaLimits}}
<tr><th>CrashDump <td>{{.CompilerProxyLog.CrashDump}}
<tr><th>Stats <td><pre>{{.CompilerProxyLog.Stats}}</pre>
<tr><th>Duration <td>{{.CompilerProxyLog.Duration}}
<tr><th>Tasks <td>{{.NumTasks}}
<tr><th>TasksPerSec <td>{{.TasksPerSec}}
</table>

{{range $mode, $bcm := .ByCompileMode}}
<h2>{{$mode}}: # of tasks: {{$bcm.NumTasks}}</h2>
<table>
 <tr><th colspan=2>replices
 {{- range $bcm.Resps}}
 <tr><th>{{.Response}}<td>{{.Num}}
 {{- end}}
 <tr><th colspan=2>duration
 <tr><th>average <td>{{$bcm.Average}}
 <tr><th>Max     <td>{{$bcm.Max}}
 {{- range $bcm.P}}
  <tr><th>{{.P}} <td>{{.D}}
 {{- end}}
 <tr><th>Min     <td>{{$bcm.Min}}
 <tr><th colspan=2>log tasks
 {{- range $i, $t := $bcm.Tasks}}
  <tr><td>{{$i}} Task:{{$t.ID}}<td>{{$t.Duration}}
   <td>{{$t.Desc}}
   <td>{{$t.Response}}
 {{- end}}
</table>
{{end}}

<h2>Duration per num active tasks</h2>
<table>
<tr><th># of tasks <th>duration <th> cumulative duration
{{range $i, $d := .DurationDistribution}}
 <tr><td>{{$i}} <td>{{$d.Duration}} <td>{{$d.CumulativeDuration}}
{{end}}
</table>

<h2>Compiler Proxy Histogram</h2>
<pre>{{.CompilerProxyLog.Histogram}}</pre>

<h2>HTTP Errors</h2>
{{range $herr, $ids := .CompilerProxyLog.HTTPErrors}}
<div>op={{$herr.Op}} code={{$herr.Code}} resp={{$herr.Resp}}</div>
<div>tasks={{$ids}}</div>
<br/>
{{end}}
</body>
</html>
`))

	compilerProxyAuthTmpl = template.Must(template.New("compiler_proxy_auth").Parse(`
<html>
<head>
 <title>compiler_proxy log</title>
</head>
<body>
{{if .User}}
{{.User.Email}} is not alow to access this page.
Please <a href="{{.Logout}}">logout</a> and login with @google.com account.
<div align="right"><a href="{{.Logout}}">logout</a></div>
{{else}}
 <div align="right"><a href="{{.Login}}">login</a></div>
You need to <a href="{{.Login}}">login</a> with @google.com account to access compiler_proxy log file.
{{end}}
</body>
</html>`))
)

func init() {
	http.Handle("/compiler_proxy_log/", http.StripPrefix("/compiler_proxy_log/", http.HandlerFunc(compilerProxyLogHandler)))
}

// compilerProxyLogHandler handles /<path> for compiler_proxy.INFO log file in gs://chrome-goma-log/<path>
func compilerProxyLogHandler(w http.ResponseWriter, req *http.Request) {
	ctx := appengine.NewContext(req)
	u := user.Current(ctx)
	if u == nil {
		authPage(w, req, http.StatusUnauthorized, compilerProxyAuthTmpl, u, path.Join("/compiler_proxy_log", req.URL.Path))
		return
	}
	if !strings.HasSuffix(u.Email, "@google.com") {
		authPage(w, req, http.StatusUnauthorized, compilerProxyAuthTmpl, u, path.Join("/compiler_proxy_log", req.URL.Path))
		return
	}

	basename := path.Base(req.URL.Path)
	if !strings.HasPrefix(basename, "compiler_proxy.") {
		log.Errorf(ctx, "wrong path is requested: %q", req.URL.Path)
		http.Error(w, "unexpected filename", http.StatusBadRequest)
		return
	}
	logPath := req.URL.Path

	cpl, err := compilerProxyLogFetch(ctx, logPath)
	if err != nil {
		log.Errorf(ctx, "failed to fetch %s: %v", logPath, err)
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}
	err = compilerProxyLogSummary(w, logPath, cpl)
	if err != nil {
		log.Errorf(ctx, "failed to output %v", err)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
}

func compilerProxyLogFetch(ctx context.Context, logPath string) (*compilerproxylog.CompilerProxyLog, error) {
	client, err := storage.NewClient(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to create storage client: %v", err)
	}
	defer client.Close()

	r, err := logstore.Fetch(ctx, client, logPath)
	if err != nil {
		return nil, err
	}
	defer r.Close()

	rd, err := gzip.NewReader(r)
	if err != nil {
		return nil, err
	}
	cpl, err := compilerproxylog.Parse(logPath, rd)
	return cpl, nil
}

type byCompileMode struct {
	Tasks    []*compilerproxylog.TaskLog
	NumTasks int
	Resps    []struct {
		Response string
		Num      int
	}
	Average time.Duration
	Max     time.Duration
	P       []struct {
		P int
		D time.Duration
	}
	Min time.Duration
}

type durationPair struct {
	Duration           time.Duration
	CumulativeDuration time.Duration
}

type compilerProxyData struct {
	Path             string
	CompilerProxyLog *compilerproxylog.CompilerProxyLog
	Tasks            []*compilerproxylog.TaskLog
	NumTasks         int
	TasksPerSec      float64

	ByCompileMode map[compilerproxylog.CompileMode]byCompileMode

	DurationDistribution []durationPair
}

func compilerProxyLogSummary(w http.ResponseWriter, logPath string, cpl *compilerproxylog.CompilerProxyLog) error {
	data := compilerProxyData{
		Path:             logPath,
		CompilerProxyLog: cpl,
		Tasks:            cpl.TaskLogs(),
		ByCompileMode:    make(map[compilerproxylog.CompileMode]byCompileMode),
	}
	data.NumTasks = len(data.Tasks)
	data.TasksPerSec = float64(data.NumTasks) / cpl.Duration().Seconds()
	var duration time.Duration
	for _, t := range data.Tasks {
		duration += t.Duration()
	}
	tasksByCompileMode := compilerproxylog.ClassifyByCompileMode(data.Tasks)
	for m, tasks := range tasksByCompileMode {
		mode := compilerproxylog.CompileMode(m)
		sort.Sort(sort.Reverse(compilerproxylog.ByDuration{TaskLogs: tasks}))
		bcm := byCompileMode{
			Tasks:    tasks,
			NumTasks: len(tasks),
		}
		if len(tasks) == 0 {
			data.ByCompileMode[mode] = bcm
			continue
		}
		if len(bcm.Tasks) > 10 {
			bcm.Tasks = bcm.Tasks[:10]
		}
		tr := compilerproxylog.ClassifyByResponse(tasks)
		var resps []string
		for r := range tr {
			resps = append(resps, r)
		}
		sort.Strings(resps)
		for _, r := range resps {
			bcm.Resps = append(bcm.Resps, struct {
				Response string
				Num      int
			}{
				Response: r,
				Num:      len(tr[r]),
			})
		}
		var duration time.Duration
		for _, t := range tasks {
			duration += t.Duration()
		}
		bcm.Average = duration / time.Duration(len(tasks))
		bcm.Max = tasks[0].Duration()
		for _, p := range []int{98, 91, 75, 50, 25, 9, 2} {
			bcm.P = append(bcm.P, struct {
				P int
				D time.Duration
			}{
				P: p,
				D: tasks[int(float64(len(tasks)*(100-p))/100.0)].Duration(),
			})
		}
		bcm.Min = tasks[len(tasks)-1].Duration()
		data.ByCompileMode[mode] = bcm
	}

	var dsum time.Duration
	for _, d := range compilerproxylog.DurationDistribution(cpl.Created, data.Tasks) {
		data.DurationDistribution = append(data.DurationDistribution, durationPair{d, d + dsum})
		dsum += d
	}

	var buf bytes.Buffer
	err := compilerProxyLogIndexTempl.Execute(&buf, data)
	if err != nil {
		return err
	}
	w.Header().Set("Content-Type", "text/html")
	_, err = w.Write(buf.Bytes())
	return err
}
