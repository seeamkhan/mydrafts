# =============================================================================
#  unified-shell.sh  —  one shared shell config for macOS (zsh) and Ubuntu (bash)
# -----------------------------------------------------------------------------
#  This single file gives every machine the same look & feel:
#    * colorized `ls`
#    * an Ubuntu-style prompt:  green user@host : blue path (yellow git-branch) $
#    * the same handy aliases (ll, la, l, .., ...)
#    * a `ghp` jump-to-projects shortcut
#
#  It detects the OS (macOS vs Linux) and the shell (zsh vs bash) at runtime,
#  so the very same file behaves correctly on both systems. It is meant to be
#  *sourced* from your ~/.zshrc or ~/.bashrc (the installer wires that up for
#  you). Re-sourcing it is safe.
# =============================================================================

# -----------------------------------------------------------------------------
# 0. Configuration  —  change this to your own GitHub username if you like.
#    `ghp` and the folder structure use it.
# -----------------------------------------------------------------------------
: "${GH_USER:=seeam}"
: "${SRC_ROOT:=$HOME/src/github.com/$GH_USER}"

# -----------------------------------------------------------------------------
# 1. Colorized `ls`
#    macOS ships BSD ls (uses -G + LSCOLORS); Linux ships GNU ls (--color).
# -----------------------------------------------------------------------------
if ls --color=auto >/dev/null 2>&1; then
  # GNU ls (Ubuntu / most Linux)
  export LS_OPTS='--color=auto'
  alias ls='ls --color=auto'
else
  # BSD ls (macOS)
  export CLICOLOR=1
  export LSCOLORS=Gxfxcxdxbxegedabagacad
  export LS_OPTS='-G'
  alias ls='ls -G'
fi

# -----------------------------------------------------------------------------
# 2. Productivity aliases  (the "Ubuntu-style detailed view")
# -----------------------------------------------------------------------------
alias ll="ls -al $LS_OPTS"   # detailed list, incl. hidden files, with colors
alias la='ls -A'             # list hidden files (no long format)
alias l='ls -CF'             # short, columnar list
alias ..='cd ..'             # go up one level
alias ...='cd ../..'         # go up two levels

# A few git quality-of-life aliases (handy for the DevOps journey)
alias gs='git status'
alias gb='git branch'
alias gl='git log --oneline --graph --decorate -20'

# -----------------------------------------------------------------------------
# 3. `ghp`  —  "GitHub Projects" jump shortcut
#    Type `ghp`            -> cd into ~/src/github.com/<user>
#    Type `ghp myrepo`     -> cd straight into that repo
# -----------------------------------------------------------------------------
ghp() {
  if [ -n "$1" ]; then
    cd "$SRC_ROOT/$1" 2>/dev/null || { echo "ghp: no such project: $1 (looked in $SRC_ROOT)"; return 1; }
  else
    cd "$SRC_ROOT" 2>/dev/null || { echo "ghp: $SRC_ROOT does not exist yet. Run the installer or: mkdir -p \"$SRC_ROOT\""; return 1; }
  fi
}

# -----------------------------------------------------------------------------
# 4. The Ubuntu-style colored prompt (with live git branch)
#    Colors:  user@host = green,  path = blue,  git branch = yellow
# -----------------------------------------------------------------------------
if [ -n "$ZSH_VERSION" ]; then
  # ---- zsh (macOS default) ----
  autoload -Uz vcs_info
  precmd() { vcs_info; }
  zstyle ':vcs_info:git:*' formats ' (%F{yellow}%b%f)'
  setopt prompt_subst
  PROMPT='%F{green}%n@%m%f:%F{blue}%~%f${vcs_info_msg_0_}$ '

elif [ -n "$BASH_VERSION" ]; then
  # ---- bash (Ubuntu default) ----
  # Small helper to print the current git branch, e.g. " (main)".
  __git_branch() {
    local b
    b=$(git symbolic-ref --quiet --short HEAD 2>/dev/null) || \
    b=$(git rev-parse --short HEAD 2>/dev/null) || return
    printf ' (%s)' "$b"
  }
  # \[\e[..m\] sequences color the prompt; \[ \] tell bash they take no width.
  #   32 = green, 34 = blue, 33 = yellow, 0 = reset
  PS1='\[\e[32m\]\u@\h\[\e[0m\]:\[\e[34m\]\w\[\e[0m\]\[\e[33m\]$(__git_branch)\[\e[0m\]$ '
fi
