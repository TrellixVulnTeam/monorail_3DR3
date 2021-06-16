// Copyright 2019 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package fileset contains an abstraction for a set of files.
package fileset

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"io"
	"io/ioutil"
	"os"
	"path"
	"path/filepath"
	"sort"
	"strings"

	"go.chromium.org/luci/common/errors"
)

// File is a file inside a file set.
type File struct {
	Path          string // file path using "/" separator
	Directory     bool   // true if this is a directory
	SymlinkTarget string // non-empty if this is a symlink

	Size       int64 // size of the file, only for regular files
	Writable   bool  // true if the file is writable, only for regular files
	Executable bool  // true if the file is executable, only for regular files

	Body func() (io.ReadCloser, error) // emits the body, only for regular files
}

// normalize clears redundant fields and converts file paths to Unix style.
//
// Returns an error if the file entry is invalid.
func (f *File) normalize() error {
	f.Path = path.Clean(filepath.ToSlash(f.Path))
	if f.Path == "." || strings.HasPrefix(f.Path, "../") {
		return errors.Reason("bad file path %q, not in the set", f.Path).Err()
	}
	switch {
	case f.Directory:
		f.SymlinkTarget = ""
		f.Size = 0
		f.Writable = false
		f.Executable = false
		f.Body = nil
	case f.SymlinkTarget != "":
		f.SymlinkTarget = path.Clean(filepath.ToSlash(f.SymlinkTarget))
		targetAbs := path.Clean(path.Join(path.Dir(f.Path), f.SymlinkTarget))
		if targetAbs == "." || strings.HasPrefix(targetAbs, "../") {
			return errors.Reason("bad symlink %q, its target %q is not in the set", f.Path, f.SymlinkTarget).Err()
		}
		f.Size = 0
		f.Writable = false
		f.Executable = false
		f.Body = nil
	}
	return nil
}

// filePerm returns FileMode with file permissions.
func (f *File) filePerm() os.FileMode {
	var mode os.FileMode = 0444
	if f.Writable {
		mode |= 0200
	}
	if f.Executable {
		mode |= 0111
	}
	return mode
}

// Excluder takes an absolute path to a file on disk and returns true or false.
type Excluder func(absPath string, isDir bool) bool

// Set represents a set of regular files, directories and symlinks.
//
// Such set can be constructed from existing files on disk (perhaps scattered
// across many directories), and it then can be written into a tarball.
type Set struct {
	files map[string]File // unix-style path inside the set => File
}

// Add adds a file or directory to the set, overriding an existing one, if any.
//
// Adds all intermediary directories, if necessary.
//
// Returns an error if the file path is invalid (e.g. starts with "../"").
func (s *Set) Add(f File) error {
	if err := f.normalize(); err != nil {
		return err
	}

	if s.files == nil {
		s.files = make(map[string]File, 1)
	}

	// Add intermediary directories. Bail if some of them are already added as
	// regular files.
	cur := ""
	for _, chr := range f.Path {
		if chr == '/' {
			switch existing, ok := s.files[cur]; {
			case !ok:
				s.files[cur] = File{Path: cur, Directory: true}
			case ok && !existing.Directory:
				return errors.Reason("%q in file path %q is not a directory", cur, f.Path).Err()
			}
		}
		cur += string(chr)
	}

	// Add the leaf file.
	s.files[f.Path] = f
	return nil
}

// AddFromDisk adds a given file or directory to the set.
//
// A file or directory located at 'fsPath' on disk will become 'setPath' in
// the set. Directories are added recursively. Symlinks are always expanded into
// whatever they point to. Broken symlinks are silently skipped. To add a
// symlink explicitly use AddSymlink.
func (s *Set) AddFromDisk(fsPath, setPath string, exclude Excluder) error {
	fsPath, err := filepath.Abs(fsPath)
	if err != nil {
		return err
	}
	setPath = path.Clean(filepath.ToSlash(setPath))
	return s.addImpl(fsPath, setPath, exclude)
}

// AddFromMemory adds the given blob to the set as a file.
//
// 'blob' is retained as a pointer, the memory is not copied.
//
// 'f', if not nil, is used to populate the file metadata. If nil, the blob is
// added as a non-executable read-only file.
func (s *Set) AddFromMemory(setPath string, blob []byte, f *File) error {
	nf := File{}
	if f != nil {
		nf = *f
	}
	nf.Path = setPath
	nf.Directory = false
	nf.Size = int64(len(blob))
	nf.Body = func() (io.ReadCloser, error) {
		return ioutil.NopCloser(bytes.NewReader(blob)), nil
	}
	return s.Add(nf)
}

// AddSymlink adds a relative symlink to the set.
//
// Doesn't verify that the target exists in the set.
func (s *Set) AddSymlink(setPath, target string) error {
	if target == "" {
		return errors.Reason("symlink target can't be empty").Err()
	}
	return s.Add(File{
		Path:          setPath,
		SymlinkTarget: target,
	})
}

// Len returns number of files in the set.
func (s *Set) Len() int {
	return len(s.files)
}

// Enumerate calls the callback for each file in the set, in alphabetical order.
//
// Returns whatever error the callback returns.
func (s *Set) Enumerate(cb func(f File) error) error {
	names := make([]string, 0, len(s.files))
	for f := range s.files {
		names = append(names, f)
	}
	sort.Strings(names)
	for _, n := range names {
		if err := cb(s.files[n]); err != nil {
			return err
		}
	}
	return nil
}

// Files returns all files in the set, in alphabetical order.
func (s *Set) Files() []File {
	out := make([]File, 0, len(s.files))
	s.Enumerate(func(f File) error {
		out = append(out, f)
		return nil
	})
	return out
}

// ToTar dumps all files in this set into a tar.Writer.
func (s *Set) ToTar(w *tar.Writer) error {
	buf := make([]byte, 64*1024)
	return s.Enumerate(func(f File) error {
		switch {
		case f.Directory:
			return w.WriteHeader(&tar.Header{
				Typeflag: tar.TypeDir,
				Name:     f.Path + "/",
				Mode:     0755,
			})
		case f.SymlinkTarget != "":
			return w.WriteHeader(&tar.Header{
				Typeflag: tar.TypeSymlink,
				Name:     f.Path,
				Linkname: f.SymlinkTarget,
				Mode:     0444,
			})
		}

		err := w.WriteHeader(&tar.Header{
			Typeflag: tar.TypeReg,
			Name:     f.Path,
			Size:     f.Size,
			Mode:     int64(f.filePerm()),
		})
		if err != nil {
			return err
		}

		r, err := f.Body()
		if err != nil {
			return err
		}
		defer r.Close()

		_, err = io.CopyBuffer(w, r, buf)
		return err
	})
}

// ToTarGz writes a *.tar.gz with files in the set to an io.Writer.
//
// Uses default compression level.
func (s *Set) ToTarGz(w io.Writer) error {
	gz := gzip.NewWriter(w)
	tb := tar.NewWriter(gz)
	if err := s.ToTar(tb); err != nil {
		tb.Close()
		gz.Close()
		return err
	}
	if err := tb.Close(); err != nil {
		gz.Close()
		return err
	}
	if err := gz.Close(); gz != nil {
		return err
	}
	return nil
}

// ToTarGzFile writes a *.tar.gz with files in the set to a file on disk.
//
// Calculates its SHA256 on the fly and returns the digest as a hex string.
func (s *Set) ToTarGzFile(path string) (sha256hex string, err error) {
	out, err := os.Create(path)
	if err != nil {
		return "", errors.Annotate(err, "failed to open for writing %s", path).Err()
	}
	defer out.Close() // for early exits
	h := sha256.New()
	if err := s.ToTarGz(io.MultiWriter(out, h)); err != nil {
		return "", errors.Annotate(err, "failed to write to %s", path).Err()
	}
	if err := out.Close(); err != nil {
		return "", errors.Annotate(err, "failed to flush %s", path).Err()
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

////////////////////////////////////////////////////////////////////////////////

// addImpl implements AddFromDisk.
func (s *Set) addImpl(fsPath, setPath string, exclude Excluder) error {
	switch stat, err := os.Stat(fsPath); {
	case os.IsNotExist(err):
		if _, lerr := os.Lstat(fsPath); lerr == nil {
			return nil // fsPath is a broken symlink, skip it
		}
		return err
	case err != nil:
		return err
	case stat.Mode().IsRegular():
		if exclude != nil && exclude(fsPath, false) {
			return nil
		}
		return s.addReg(fsPath, setPath, stat)
	case stat.Mode().IsDir():
		if exclude != nil && exclude(fsPath, true) {
			return nil
		}
		return s.addDir(fsPath, setPath, exclude)
	default:
		return errors.Reason("file %q has unsupported type, its mode is %s", fsPath, stat.Mode()).Err()
	}
}

// addReg adds a regular file to the set.
func (s *Set) addReg(fsPath, setPath string, fi os.FileInfo) error {
	return s.Add(File{
		Path:       setPath,
		Size:       fi.Size(),
		Writable:   (fi.Mode() & 0222) != 0,
		Executable: (fi.Mode() & 0111) != 0,
		Body:       func() (io.ReadCloser, error) { return os.Open(fsPath) },
	})
}

// addDir recursively adds a directory to the set.
func (s *Set) addDir(fsPath, setPath string, exclude Excluder) error {
	// Don't add the set root itself, it is always implied. Allowing it explicitly
	// causes complication related to dealing with ".".
	if setPath != "." {
		if err := s.Add(File{Path: setPath, Directory: true}); err != nil {
			return err
		}
	}

	f, err := os.Open(fsPath)
	if err != nil {
		return err
	}
	files, err := f.Readdirnames(-1)
	if err != nil {
		return err
	}
	f.Close()

	for _, f := range files {
		if err := s.addImpl(filepath.Join(fsPath, f), path.Join(setPath, f), exclude); err != nil {
			return err
		}
	}

	return nil
}
