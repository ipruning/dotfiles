let prefer = [
  $"($env.HOME)/.local/bin"
  $"($env.HOME)/dotfiles/config/shell/bin"
  $"($env.HOME)/Developer/prototypes/utils/scripts"
  $"($env.HOME)/Developer/prototypes/utils/bin"
  "/opt/homebrew/bin"
]

$env.PATH = (
  $prefer
  | append $env.PATH
  | flatten
  | reduce -f [] {|p acc| if ($acc | any {|x| $x == $p}) { $acc } else { $acc ++ [$p] } }
)
