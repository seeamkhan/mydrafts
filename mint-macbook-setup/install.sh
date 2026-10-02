#!/usr/bin/env bash
# Install the Mac-style tweaks (keyd keyboard, three-finger drag, macmode toggle).
# Usage:  sudo ./install.sh        (from your normal user account)
# Undo:   sudo ./uninstall.sh
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo: sudo $0" >&2; exit 1; }
U=${SUDO_USER:?Run this with sudo from your normal user account}
H=$(getent passwd "$U" | cut -d: -f6)
HERE=$(cd "$(dirname "$0")" && pwd)

KEYD_TAG=v2.6.0
KEYD_SRC=$H/.local/src/keyd
DRAG_URL=https://github.com/marsqing/libinput-three-finger-drag/releases/download/0.2/libinput-three-finger-drag.tgz
DRAG_SHA256=26c1f29680a1fb077487bc6ad57a5f2d38192e1eb8556a20642b51786be7f29d
BACKUP=$H/mint-macbook-backup-$(date +%F)
QUIRKS=/etc/libinput/local-overrides.quirks

as_user() { sudo -u "$U" -H "$@"; }
step()    { printf '\n==> %s\n' "$*"; }

step "Packages: libxdo3 (three-finger drag), python3-xlib (keyd app mapper)"
apt-get install -y libxdo3 python3-xlib

step "keyd $KEYD_TAG: build and install"
if [ ! -x "$KEYD_SRC/bin/keyd" ]; then
    as_user mkdir -p "$(dirname "$KEYD_SRC")"
    as_user git clone -q --depth 1 --branch "$KEYD_TAG" https://github.com/rvaiya/keyd.git "$KEYD_SRC"
    as_user make -C "$KEYD_SRC"
fi
make -C "$KEYD_SRC" install
chown -R "$U": "$KEYD_SRC"
getent group keyd >/dev/null || groupadd --system keyd

step "keyd config (built-in keyboard only)"
as_user mkdir -p "$BACKUP/etc"
[ -f /etc/keyd/default.conf ] && cp /etc/keyd/default.conf "$BACKUP/etc/keyd-default.conf"
install -Dm644 "$HERE/keyd/default.conf" /etc/keyd/default.conf
keyd check /etc/keyd/default.conf

step "libinput quirk: keep disable-while-typing working with keyd"
mkdir -p /etc/libinput
if [ -f "$QUIRKS" ]; then
    cp "$QUIRKS" "$BACKUP/etc/"
    grep -q 'keyd virtual keyboard' "$QUIRKS" || { echo; cat "$HERE/libinput/local-overrides.quirks"; } >> "$QUIRKS"
else
    install -m644 "$HERE/libinput/local-overrides.quirks" "$QUIRKS"
fi

step "On/off support: state dir, service condition, passwordless start/stop for the keyd group"
install -d -m 2775 -o root -g keyd /var/lib/macmode
install -Dm644 /dev/stdin /etc/systemd/system/keyd.service.d/macmode.conf <<'EOF'
# Written by mint-macbook-setup: `macmode off keyboard` creates this flag file.
[Unit]
ConditionPathExists=!/var/lib/macmode/keyboard.off
EOF
install -Dm644 /dev/stdin /etc/polkit-1/rules.d/50-macmode-keyd.rules <<'EOF'
// Written by mint-macbook-setup: members of "keyd" may start/stop keyd.service (macmode toggle).
polkit.addRule(function(action, subject) {
    if (action.id == "org.freedesktop.systemd1.manage-units" &&
        action.lookup("unit") == "keyd.service" &&
        subject.isInGroup("keyd")) {
        var verb = action.lookup("verb");
        if (verb == "start" || verb == "stop" || verb == "restart") {
            return polkit.Result.YES;
        }
    }
});
EOF

step "Three-finger drag helper"
tmp=$(mktemp -d)
curl -fsSL -o "$tmp/drag.tgz" "$DRAG_URL"
echo "$DRAG_SHA256  $tmp/drag.tgz" | sha256sum -c -
tar xzf "$tmp/drag.tgz" -C "$tmp"
install -m755 "$tmp/libinput-three-finger-drag" /usr/local/bin/libinput-three-finger-drag
rm -rf "$tmp"

step "Groups: $U -> keyd (toggle keyd), input (three-finger drag reads the trackpad)"
usermod -aG keyd,input "$U"

step "User files"
A=$H/.config/autostart
as_user mkdir -p "$A" "$H/.config/keyd" "$H/.local/bin" "$H/.local/share/applications" "$BACKUP/autostart"
if [ -f "$A/Swap Cmd and Ctrl.desktop" ]; then
    mv "$A/Swap Cmd and Ctrl.desktop" "$BACKUP/autostart/"   # keyd replaces the setxkbmap swap
fi
as_user install -m644 "$HERE/keyd/app.conf" "$H/.config/keyd/app.conf"
as_user install -m755 "$HERE/macmode" "$H/.local/bin/macmode"

# macmode starts the touchegg client itself, so hide the system autostart entry.
as_user sh -c "sed '/^Hidden=/d' /etc/xdg/autostart/touchegg.desktop > '$A/touchegg.desktop' && echo Hidden=true >> '$A/touchegg.desktop'"

as_user tee "$A/macmode.desktop" >/dev/null <<EOF
[Desktop Entry]
Type=Application
Name=Mac Mode (apply at login)
Exec=$H/.local/bin/macmode apply
OnlyShowIn=XFCE;
Terminal=false
Hidden=false
EOF
as_user tee "$H/.local/share/applications/macmode.desktop" >/dev/null <<EOF
[Desktop Entry]
Type=Application
Name=Mac Mode
Comment=Turn the Mac-style keyboard, three-finger drag and gestures on or off
Exec=$H/.local/bin/macmode
Icon=input-keyboard
Categories=Settings;
Terminal=false
EOF

step "Start keyd"
systemctl daemon-reload
systemctl enable keyd
[ -e /var/lib/macmode/keyboard.off ] || systemctl restart keyd
# Remove the old X-level swap from the running session so it doesn't stack with keyd.
as_user env DISPLAY="${DISPLAY:-:0}" XAUTHORITY="$H/.Xauthority" setxkbmap -option '' -option terminate:ctrl_alt_bksp || true

chown -R "$U": "$BACKUP"

cat <<EOF

Done. Backups: $BACKUP
Now LOG OUT and log back in (needed for the new groups).
Then: menu > Settings > "Mac Mode" (GUI), or run: macmode status
EOF
