# emma
Configures the operating mode of emagic MIDI devices (UNITOR8,AMT8,MT4) on Linux

Install:

  emma.pl is a Perl script, so of course you need Perl installed.

  Additionally, you'll need the following Perl-Modules installed:

    - MIDI::ALSA
    - String::HexConvert

  Find them in your software repo or do a cpan install [NAME].

Usage:
    emma.pl [options]

Options:
    emma.pl <MODE> <PORT>

    -m/--mode=MODE
        Operating Mode (patch/usb) to set

    -p/--port=PORT
        Target MIDI port (UNITOR8,AMT8,MT4)

    -h/--help
        Help

    -v/--version
        version information

