Prerequisiti:

#. fare un dump del database con auto_backup (o in alternativa manualmente)
#. estrarre il backup e copiare il file .sql e la cartella filestore) nella cartella home dell'utente attuale (/home/<utente>/) (o in alternativa copiare i file backuppati manualmente .gz e .tar)
#. aprire una console di python 3.6 (o 3.7) in cui siano installate le dipendenze per la migrazione
#. aprire la connessione con:

Migrazione:

.. code-block:: python
    from main import openupgrader
    mig = openupgrader.Connection('db', 'amministratore_db', 'password', '5441')

n.b.: i parametri sono:

- il database da migrare,
- l'utente amministratore,
- la password amministratore,
- un cluster di postgres dove fare la migrazione (può anche essere quello di default, comunque al minimo di versione uguale a quello in uso sul db da migrare)

#. avviare la migrazione alla versione successiva con:

.. code-block:: python
    mig.init_migration('12.0', '13.0', restore_db_update=True, filestore=True)

n.b. il parametro 'restore_db_update' va messo a True per il primo passaggio di versione solo, il filestore solo se è presente (per istanze con filestore ingestibile si può pensare di far senza)

.. code-block:: python
    mig.prepare_migration()
    mig.do_migration()

#. nella cartella autogenerata 'tmp_venv' nella cartella attuale si troveranno:
   - le copie di backup delle varie versioni del database, del filestore e dei requirements
   - le directory con le varie installazioni di versione con all'interno (tra l'altro) il log della migrazione della specifica versione.
#. n.b. è possibile ripartire da una migrazione in corso da una qualsiasi versione intermedia, tipo da 11.0 a 12.0 non è andata bene per qualcosa, si rilancia come da punto 5. con:

.. code-block:: python
    mig.init_migration('11.0', '12.0', restore_db_only=True, filestore=True)
    mig.prepare_migration()
    mig.do_migration()

n.b. restore_db_only ripristina il db migrato alla versione iniziale indicata, mentre restore_db_update fa inoltre l'aggiornamento con -u all
