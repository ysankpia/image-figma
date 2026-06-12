package detector

import (
	"fmt"
	"image"
	"image/draw"
	"math"
	"strings"
)

type PassSpec struct {
	ID           string
	Kind         string
	PromptName   string
	SourceBBox   BBox
	Prompt       string
	AllowedRoles map[Role]bool
}

type preparedPass struct {
	Spec       PassSpec
	Run        PassRun
	Image      image.Image
	Prompt     string
	SourceSize image.Point
}

func preparePasses(src image.Image, names []string, maxSide int) ([]preparedPass, error) {
	bounds := src.Bounds()
	sourceSize := image.Pt(bounds.Dx(), bounds.Dy())
	out := make([]preparedPass, 0, len(names))
	for _, name := range names {
		spec, err := passSpec(strings.TrimSpace(name), sourceSize)
		if err != nil {
			return nil, err
		}
		cropped := cropImage(src, spec.SourceBBox)
		resized := resizeToMaxSide(cropped, maxSide)
		rb := resized.Bounds()
		out = append(out, preparedPass{
			Spec: spec,
			Run: PassRun{
				ID:         spec.ID,
				Kind:       spec.Kind,
				PromptName: spec.PromptName,
				SourceBBox: spec.SourceBBox,
				SentWidth:  rb.Dx(),
				SentHeight: rb.Dy(),
				MaxSide:    maxSide,
			},
			Image:      resized,
			Prompt:     spec.Prompt,
			SourceSize: sourceSize,
		})
	}
	return out, nil
}

func passSpec(name string, size image.Point) (PassSpec, error) {
	full := BBox{X: 0, Y: 0, Width: float64(size.X), Height: float64(size.Y)}
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "", "full":
		return passSpec("layout", size)
	case "layout":
		return PassSpec{
			ID:         "layout",
			Kind:       "role_focus",
			PromptName: "major_layout_regions",
			SourceBBox: full,
			Prompt: rolePrompt(`Detect only major mobile UI layout regions in this screenshot.
Include visible status/action/top chrome, main content list, bottom navigation, side rails, repeated content bands, and major cards.
Do not output every text label or tiny icon.
Do not output final hierarchy.
Return coarse candidates only.`),
			AllowedRoles: roleSet(RoleStatusBar, RoleActionBar, RoleBottomNavigation, RoleListView, RoleViewGroup, RoleBackground, RoleEditText),
		}, nil
	case "imageview", "images", "icons":
		return PassSpec{
			ID:         "imageview",
			Kind:       "role_focus",
			PromptName: "concrete_images_and_icons",
			SourceBBox: full,
			Prompt: rolePrompt(`Detect only concrete visible image/icon elements.
Include thumbnails, cover images, avatars, badges, arrows, status glyphs, navigation icons, small UI icons, and image-like decorative glyphs.
Do not output text labels as TextView.
Do not output containers, buttons, backgrounds, or final hierarchy.
Prefer tight visible bboxes for the image/icon itself.`),
			AllowedRoles: roleSet(RoleImageView),
		}, nil
	case "background", "surfaces":
		return PassSpec{
			ID:         "background",
			Kind:       "role_focus",
			PromptName: "visible_background_surfaces",
			SourceBBox: full,
			Prompt: rolePrompt(`Detect only visible background and surface regions.
Include cards, bars, pills, panels, selected tab surfaces, obvious large background blocks, and visible control backplates.
Do not output text, icons, buttons, or final hierarchy.
Do not infer invisible containers.`),
			AllowedRoles: roleSet(RoleBackground),
		}, nil
	case "bottom_nav", "bottom-navigation", "bottomnav":
		box := bandBBox(size, 0, 0.82, 1, 0.18)
		return PassSpec{
			ID:         "bottom_nav",
			Kind:       "crop_focus",
			PromptName: "bottom_navigation",
			SourceBBox: box,
			Prompt: rolePrompt(`Detect the bottom navigation area in this cropped mobile UI.
Include the BottomNavigation container and concrete tab icons.
Do not output every text label unless it is needed as a sparse tab label hint.
Do not create Button candidates for each tab.`),
			AllowedRoles: roleSet(RoleBottomNavigation, RoleImageView, RoleTextView, RoleBackground, RoleViewGroup),
		}, nil
	case "top_chrome", "top", "chrome":
		box := bandBBox(size, 0, 0, 1, 0.18)
		return PassSpec{
			ID:         "top_chrome",
			Kind:       "crop_focus",
			PromptName: "top_chrome",
			SourceBBox: box,
			Prompt: rolePrompt(`Detect visible top chrome elements in this cropped mobile UI.
Focus on status bar glyphs, action bar icons, search/input fields, tabs, selected indicators, and top control surfaces.
Do not output final hierarchy.`),
			AllowedRoles: roleSet(RoleStatusBar, RoleActionBar, RoleImageView, RoleEditText, RoleBackground, RoleViewGroup, RoleTextView),
		}, nil
	case "right_rail", "right", "rail":
		box := bandBBox(size, 0.78, 0.12, 0.22, 0.78)
		return PassSpec{
			ID:         "right_rail",
			Kind:       "crop_focus",
			PromptName: "right_rail",
			SourceBBox: box,
			Prompt: rolePrompt(`Detect visible right-side rail elements in this cropped mobile UI.
Focus on vertical thumbnails, rail markers, side list items, and concrete icons.
Do not output unrelated text labels or final hierarchy.`),
			AllowedRoles: roleSet(RoleImageView, RoleListView, RoleViewGroup, RoleBackground, RoleTextView),
		}, nil
	case "search_bar", "search":
		box := bandBBox(size, 0, 0.07, 1, 0.14)
		return PassSpec{
			ID:         "search_bar",
			Kind:       "crop_focus",
			PromptName: "search_bar",
			SourceBBox: box,
			Prompt: rolePrompt(`Detect the visible search/input bar and its local icons in this cropped mobile UI.
Include EditText/search field surfaces and concrete icons.
Do not output final hierarchy.`),
			AllowedRoles: roleSet(RoleEditText, RoleImageView, RoleBackground, RoleTextView),
		}, nil
	default:
		return PassSpec{}, fmt.Errorf("unsupported detector pass %q", name)
	}
}

func rolePrompt(task string) string {
	return strings.TrimSpace(`You are a precise mobile UI detector.
Return ONLY JSON.
Use normalized coordinates relative to the received image.
Coordinates must be [x1,y1,x2,y2], each value from 0 to 1.
Detect concrete visible UI elements, not inferred semantics.
Roles must be one of: ImageView, TextView, Background, StatusBar, ActionBar, BottomNavigation, ListView, ViewGroup, Button, EditText.
Return this shape:
{"elements":[{"role":"ImageView","label":"short label","confidence":0.90,"bbox":[0.10,0.20,0.30,0.40]}]}

` + task)
}

func roleSet(roles ...Role) map[Role]bool {
	out := make(map[Role]bool, len(roles))
	for _, role := range roles {
		out[role] = true
	}
	return out
}

func bandBBox(size image.Point, x, y, w, h float64) BBox {
	return BBox{
		X:      math.Round(x * float64(size.X)),
		Y:      math.Round(y * float64(size.Y)),
		Width:  math.Round(w * float64(size.X)),
		Height: math.Round(h * float64(size.Y)),
	}
}

func cropImage(src image.Image, bbox BBox) image.Image {
	sb := src.Bounds()
	x1 := clampInt(int(math.Round(bbox.X)), 0, sb.Dx())
	y1 := clampInt(int(math.Round(bbox.Y)), 0, sb.Dy())
	x2 := clampInt(int(math.Round(bbox.X+bbox.Width)), x1+1, sb.Dx())
	y2 := clampInt(int(math.Round(bbox.Y+bbox.Height)), y1+1, sb.Dy())
	rect := image.Rect(0, 0, x2-x1, y2-y1)
	out := image.NewRGBA(rect)
	draw.Draw(out, rect, src, image.Pt(sb.Min.X+x1, sb.Min.Y+y1), draw.Src)
	return out
}

func resizeToMaxSide(src image.Image, maxSide int) image.Image {
	b := src.Bounds()
	w := b.Dx()
	h := b.Dy()
	if maxSide <= 0 || (w <= maxSide && h <= maxSide) {
		return src
	}
	scale := float64(maxSide) / float64(max(w, h))
	nw := max(1, int(math.Round(float64(w)*scale)))
	nh := max(1, int(math.Round(float64(h)*scale)))
	out := image.NewRGBA(image.Rect(0, 0, nw, nh))
	for y := 0; y < nh; y++ {
		sy := b.Min.Y + clampInt(int(float64(y)/scale), 0, h-1)
		for x := 0; x < nw; x++ {
			sx := b.Min.X + clampInt(int(float64(x)/scale), 0, w-1)
			out.Set(x, y, src.At(sx, sy))
		}
	}
	return out
}

func clampInt(value, low, high int) int {
	if value < low {
		return low
	}
	if value > high {
		return high
	}
	return value
}
