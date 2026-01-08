
-- QUERY DI VERIFICA
-- Esegui questo script per vedere la definizione attuale delle policy.
-- Se vedi '(SELECT current_setting...)' allora lo script di ottimizzazione ha FUNZIONATO.
-- Se vedi solo 'current_setting...' (senza SELECT e parentesi attorno), allora NON ha funzionato.

SELECT 
    tablename, 
    policyname, 
    cmd, 
    qual, 
    with_check 
FROM 
    pg_policies 
WHERE 
    tablename IN ('conti', 'configurazioni') 
ORDER BY 
    tablename, policyname;
