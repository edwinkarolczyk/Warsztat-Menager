import gui_profile as gp


def test_deadline_sorting_and_default():
    tasks = gp._read_tasks('sort_test')
    deadlines = [t['termin'] for t in tasks]
    # Zadania powinny być posortowane rosnąco po terminie
    assert deadlines == sorted(deadlines)
    # Ostatnie zadanie powinno mieć domyślną datę końcową
    assert deadlines[-1] == gp.DEFAULT_TASK_DEADLINE
    # Wszystkie wcześniejsze zadania powinny mieć własne terminy
    assert all(d != gp.DEFAULT_TASK_DEADLINE for d in deadlines[:-1])
