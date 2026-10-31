{
  description = "Imprint firmware build and keymap checks";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
  outputs =
    { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            just
            git
            podman
            python3
            gcc
          ];
          XKB_CONFIG_ROOT = "${pkgs.xkeyboard_config}/share/X11/xkb";
          XKB_LIBRARY = "${pkgs.libxkbcommon}/lib/libxkbcommon.so.0";
          shellHook = ''echo "Imprint: run just for available commands"'';
        };
      });
      formatter = forAllSystems (pkgs: pkgs.nixfmt);
    };
}
