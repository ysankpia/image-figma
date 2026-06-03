package storage

import "path/filepath"

const DefaultRoot = "./storage/pencil_server"

type Paths struct {
	Root string
}

func New(root string) Paths {
	if root == "" {
		root = DefaultRoot
	}
	return Paths{Root: root}
}

func (p Paths) TaskRoot(taskID string) string {
	return filepath.Join(p.Root, "projects", taskID)
}

func (p Paths) UploadsDir(taskID string) string {
	return filepath.Join(p.TaskRoot(taskID), "uploads")
}

func (p Paths) OutputDir(taskID string) string {
	return filepath.Join(p.TaskRoot(taskID), "output")
}
