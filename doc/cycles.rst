=================
Looking at Cycles
=================

.. figure:: _images/cycles.png

    Two plots providing a rough analysis of the situation for one bead. On the
    left are cycles superposed one on the other. On the right are histograms
    indicating the number of cycles (*rate*) and the number of values
    (*duration*) at a given :math:`z` position.

This tab provides information which will be extracted automatically in either
of the 2 tabs to the left. It exists for historical reasons but also allows
fitting manually to a hairpin sequence. This might be helpful should
automations fail. It's still good practice to report such situations if they
happen too often.

Hairpins and Oligos
===================

Choosing Sequences
------------------

A sequence file can be indicated using the left-most dropdown menu. The files
should in fasta format:

    > sequence 1
    aaattcgaAATTcgaaattcgaaattcg
    attcgaaaTTCGaaattcgaaattcgaa

    > sequence 2
    aaattcgaaattcgaaattcgaaattcg
    attcgaaattcgaaattcgaaattcgaa

In this case, two different sequences were provided. The line starting with `>`
should contain the name of the sequence. The next lines will all be part of the
sequence until the next line starting with `>`. The sequence can be in
uppercase or not. No checks are made on the alphabet although the software will
find peak positions only where letters 'a', 't', 'c' or 'g' or their uppercase
are used. In other words, replacing parts of the sequence by 'NNNN' ensures the
software will not use that part of the sequence without changing the latter's
size. The letter 'u' is not recognized either!

Choosing Oligos
---------------

The text box below allows setting one or more oligos. Multiple oligos should be
separated by comas. The positions found can be on *either* strands.

Complex Expressions
^^^^^^^^^^^^^^^^^^^
The following alphabet is recognized, allowing for more complex expressions:

* k: either g or t
* m: either a or c
* r: either a or g
* y: either c or t
* s: either c or g
* w: either a or t
* b: any but a
* v: any but t
* h: any but g
* d: any but c
* u: t
* n or x or .: any

Blocking Position in the Oligo
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Positions are at the end of the oligos rather than the start as the former is
where the fork blocks. In other words, given a sequence as follows, oligo TAC
will block at position 110 rather than 108::

                  3'-CAT-5'
    5'-(...)cccatattcGTAtcgtcccat(...)-3'
            :          :
            100        110

Such a behaviour doesn't work for antibodies when, for example, looking for
'CCWGG' positions in which the 'W' is methylated. In that case one can use a
'!' to mark the position to use instead. In the following example, 'cc!wgg'
will find a position at 110::

    5'-(...)cccatatttCCWGGcgtcccat(...)-3'
            :          :
            100        110

