{ pkgs ? import <nixpkgs> {} }:

let
  python-pkgs = pp: with pp; [
    # tools
    black
    flake8

    # deps
    udatetime
  ];
  python = pkgs.python3.withPackages python-pkgs;
in
pkgs.mkShell {
  nativeBuildInputs = [
    python
  ];
}
