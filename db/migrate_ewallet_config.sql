-- Migration to add specialized configuration column to accounts
-- This column will store encrypted JSON settings for Satispay and PayPal

-- Add column to personal accounts table
ALTER TABLE Conti ADD COLUMN config_speciale TEXT;

-- Add column to shared accounts table
ALTER TABLE ContiCondivisi ADD COLUMN config_speciale TEXT;
