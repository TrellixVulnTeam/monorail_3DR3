// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package fileset

import (
	"archive/tar"
	"bytes"
	"fmt"
	"io"
	"io/ioutil"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	. "github.com/smartystreets/goconvey/convey"
	. "go.chromium.org/luci/common/testing/assertions"
)

func TestSet(t *testing.T) {
	t.Parallel()

	Convey("Regular files", t, func(c C) {
		dir1 := newTempDir(c)
		dir1.touch("f1")
		dir1.mkdir("dir")
		dir1.touch("dir/a")
		dir1.mkdir("dir/empty")
		dir1.mkdir("dir/nested")
		dir1.touch("dir/nested/f")

		dir2 := newTempDir(c)
		dir2.touch("f2")
		dir2.mkdir("dir")
		dir2.touch("dir/b")

		dir3 := newTempDir(c)
		dir3.touch("f")

		s := &Set{}
		So(s.AddFromDisk(dir1.join(""), "", nil), ShouldBeNil)
		So(s.AddFromDisk(dir2.join(""), "", nil), ShouldBeNil)
		So(s.AddFromDisk(dir3.join(""), "dir/deep/", nil), ShouldBeNil)
		So(s.AddFromMemory("mem", nil, nil), ShouldBeNil)
		So(s.Len(), ShouldEqual, 11)
		So(collect(s), ShouldResemble, []string{
			"D dir",
			"F dir/a",
			"F dir/b",
			"D dir/deep",
			"F dir/deep/f",
			"D dir/empty",
			"D dir/nested",
			"F dir/nested/f",
			"F f1",
			"F f2",
			"F mem",
		})
	})

	Convey("Symlinks", t, func() {
		addOne := func(path, target string) (*File, error) {
			s := Set{}
			if err := s.AddSymlink(path, target); err != nil {
				return nil, err
			}
			for _, f := range s.Files() {
				if !f.Directory {
					return &f, nil
				}
			}
			panic("impossible")
		}

		f, err := addOne("path", "target")
		So(err, ShouldBeNil)
		So(f, ShouldResemble, &File{
			Path:          "path",
			SymlinkTarget: "target",
		})

		f, err = addOne("a/b/c/path", "target")
		So(err, ShouldBeNil)
		So(f, ShouldResemble, &File{
			Path:          "a/b/c/path",
			SymlinkTarget: "target",
		})

		f, err = addOne("a/b/c/path", ".././.")
		So(err, ShouldBeNil)
		So(f, ShouldResemble, &File{
			Path:          "a/b/c/path",
			SymlinkTarget: "..",
		})

		f, err = addOne("a/b/c/path", "../..")
		So(err, ShouldBeNil)
		So(f, ShouldResemble, &File{
			Path:          "a/b/c/path",
			SymlinkTarget: "../..",
		})

		_, err = addOne("a/b/c/path", "../../..")
		So(err, ShouldErrLike, "is not in the set")
	})

	Convey("Reading body", t, func(c C) {
		s := &Set{}

		dir1 := newTempDir(c)
		dir1.put("f", "1", 0666)
		So(s.AddFromDisk(dir1.join(""), "", nil), ShouldBeNil)

		files := s.Files()
		So(files, ShouldHaveLength, 1)
		So(read(files[0]), ShouldEqual, "1")

		dir2 := newTempDir(c)
		dir2.put("f", "2", 0666)
		So(s.AddFromDisk(dir2.join(""), "", nil), ShouldBeNil)

		// Overwritten.
		files = s.Files()
		So(files, ShouldHaveLength, 1)
		So(read(files[0]), ShouldEqual, "2")
	})

	Convey("Reading memfile", t, func(c C) {
		s := &Set{}
		So(s.AddFromMemory("mem", []byte("123456"), &File{
			Writable:   true,
			Executable: true,
		}), ShouldBeNil)
		files := s.Files()
		So(files, ShouldHaveLength, 1)
		So(files[0].Writable, ShouldBeTrue)
		So(files[0].Executable, ShouldBeTrue)
		So(read(files[0]), ShouldEqual, "123456")
	})

	if runtime.GOOS != "windows" {
		Convey("Recognizes read-only", t, func(c C) {
			s := &Set{}

			dir := newTempDir(c)
			dir.put("ro", "", 0444)
			dir.put("rw", "", 0666)
			So(s.AddFromDisk(dir.join(""), "", nil), ShouldBeNil)

			files := s.Files()
			So(files, ShouldHaveLength, 2)
			So(files[0].Writable, ShouldBeFalse)
			So(files[1].Writable, ShouldBeTrue)
		})

		Convey("Recognizes executable", t, func(c C) {
			s := &Set{}

			dir := newTempDir(c)
			dir.put("n", "", 0666)
			dir.put("y", "", 0777)
			So(s.AddFromDisk(dir.join(""), "", nil), ShouldBeNil)

			files := s.Files()
			So(files, ShouldHaveLength, 2)
			So(files[0].Executable, ShouldBeFalse)
			So(files[1].Executable, ShouldBeTrue)
		})

		Convey("Follows symlinks", t, func(c C) {
			dir := newTempDir(c)
			dir.touch("file")
			dir.mkdir("dir")
			dir.touch("dir/a")
			dir.mkdir("stage")
			dir.symlink("stage/filelink", "file")
			dir.symlink("stage/dirlink", "dir")
			dir.symlink("stage/broken", "broken") // skipped

			s := &Set{}
			So(s.AddFromDisk(dir.join("stage"), "", nil), ShouldBeNil)
			So(collect(s), ShouldResemble, []string{
				"D dirlink",
				"F dirlink/a",
				"F filelink",
			})
		})
	}

	Convey("ToTar works", t, func(c C) {
		s := prepSet()

		buf := bytes.Buffer{}
		tb := tar.NewWriter(&buf)
		So(s.ToTar(tb), ShouldBeNil)
		So(tb.Close(), ShouldBeNil)

		scan := &Set{}
		tr := tar.NewReader(&buf)
		for {
			hdr, err := tr.Next()
			if err == io.EOF {
				break
			}
			So(err, ShouldBeNil)

			if hdr.Typeflag == tar.TypeDir {
				scan.Add(File{
					Path:      hdr.Name,
					Directory: true,
				})
				continue
			}

			if hdr.Typeflag == tar.TypeSymlink {
				scan.AddSymlink(hdr.Name, hdr.Linkname)
				continue
			}

			body := bytes.Buffer{}
			_, err = io.Copy(&body, tr)
			So(err, ShouldBeNil)

			f := memFile(hdr.Name, string(body.Bytes()))
			if runtime.GOOS != "windows" {
				f.Writable = (hdr.Mode & 0222) != 0
				f.Executable = (hdr.Mode & 0111) != 0
			}
			scan.Add(f)
		}

		assertEqualSets(s, scan)
	})

	Convey("ToTarGz works", t, func(c C) {
		buf := bytes.Buffer{}
		So(prepSet().ToTarGz(&buf), ShouldBeNil)
		So(buf.Len(), ShouldNotEqual, 0) // writes something...
	})

	Convey("ToTarGzFile works", t, func(c C) {
		hash, err := prepSet().ToTarGzFile(newTempDir(c).join("tmp"))
		So(err, ShouldBeNil)
		So(hash, ShouldHaveLength, 64)
	})
}

func collect(s *Set) []string {
	out := []string{}
	s.Enumerate(func(f File) error {
		t := "F"
		if f.Directory {
			t = "D"
		}
		out = append(out, fmt.Sprintf("%s %s", t, f.Path))
		return nil
	})
	return out
}

func read(f File) string {
	if f.Directory || f.SymlinkTarget != "" {
		return ""
	}
	r, err := f.Body()
	So(err, ShouldBeNil)
	defer r.Close()
	body, err := ioutil.ReadAll(r)
	So(err, ShouldBeNil)
	return string(body)
}

func prepSet() *Set {
	s := &Set{}
	s.Add(memFile("f", "hello"))
	s.Add(File{Path: "dir", Directory: true})
	s.Add(memFile("dir/f", "another"))
	s.AddSymlink("dir/link", "f")

	rw := memFile("rw", "read-write")
	rw.Writable = true
	s.Add(rw)

	exe := memFile("exe", "executable")
	exe.Executable = runtime.GOOS != "windows"
	s.Add(exe)

	return s
}

func memFile(path, body string) File {
	return File{
		Path:     path,
		Size:     int64(len(body)),
		Writable: runtime.GOOS == "windows", // FileMode perms don't work on windows
		Body: func() (io.ReadCloser, error) {
			return ioutil.NopCloser(strings.NewReader(body)), nil
		},
	}
}

func assertEqualSets(a, b *Set) {
	aMeta, aBodies := splitBodies(a.Files())
	bMeta, bBodies := splitBodies(b.Files())
	So(aMeta, ShouldResemble, bMeta)
	So(aBodies, ShouldResemble, bBodies)
}

func splitBodies(fs []File) (files []File, bodies map[string]string) {
	files = make([]File, len(fs))
	bodies = make(map[string]string, len(fs))
	for i, f := range fs {
		bodies[f.Path] = read(f)
		f.Body = nil
		files[i] = f
	}
	return
}

type tmpDir struct {
	p string
	c C
}

func newTempDir(c C) tmpDir {
	tmp, err := ioutil.TempDir("", "fileset_test")
	c.So(err, ShouldBeNil)
	c.Reset(func() { os.RemoveAll(tmp) })
	return tmpDir{tmp, c}
}

func (t tmpDir) join(p string) string {
	return filepath.Join(t.p, filepath.FromSlash(p))
}

func (t tmpDir) mkdir(p string) {
	t.c.So(os.MkdirAll(t.join(p), 0777), ShouldBeNil)
}

func (t tmpDir) put(p, data string, mode os.FileMode) {
	f, err := os.OpenFile(t.join(p), os.O_CREATE|os.O_WRONLY, mode)
	t.c.So(err, ShouldBeNil)
	_, err = f.Write([]byte(data))
	t.c.So(err, ShouldBeNil)
	t.c.So(f.Close(), ShouldBeNil)
}

func (t tmpDir) touch(p string) {
	t.put(p, "", 0666)
}

func (t tmpDir) symlink(name, target string) {
	So(os.Symlink(t.join(target), t.join(name)), ShouldBeNil)
}
