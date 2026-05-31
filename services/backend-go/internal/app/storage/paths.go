package storage

import "path/filepath"

const DefaultRoot = "./storage/draft_server"

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
	return filepath.Join(p.Root, "draft_previews", taskID)
}

func (p Paths) SourcePath(taskID string) string {
	return filepath.Join(p.TaskRoot(taskID), "source.png")
}

func (p Paths) DraftDir(taskID string) string {
	return filepath.Join(p.TaskRoot(taskID), "draft")
}

func (p Paths) AssetsDir(taskID string) string {
	return filepath.Join(p.TaskRoot(taskID), "assets")
}
