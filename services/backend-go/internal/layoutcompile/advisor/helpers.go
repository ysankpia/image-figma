package advisor

import "sort"

func median(values []int) int {
	if len(values) == 0 {
		return 0
	}
	out := append([]int(nil), values...)
	sort.Ints(out)
	mid := len(out) / 2
	if len(out)%2 == 1 {
		return out[mid]
	}
	return (out[mid-1] + out[mid]) / 2
}

func variance(values []int) int {
	if len(values) <= 1 {
		return 0
	}
	mean := 0
	for _, value := range values {
		mean += value
	}
	mean /= len(values)
	total := 0
	for _, value := range values {
		delta := value - mean
		total += delta * delta
	}
	return total / len(values)
}

func maxSlice(values []int) int {
	out := 0
	for _, value := range values {
		if value > out {
			out = value
		}
	}
	return out
}

func max(a int, b int) int {
	if a > b {
		return a
	}
	return b
}
