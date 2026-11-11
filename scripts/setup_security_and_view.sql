-- Run as a database administrator after ingesting the sample table.
-- Provision a SQL login USR_FDE_RO with a unique password separately using your
-- database administration tool. No shared sample password is stored in this file.
IF SCHEMA_ID('FDE_VIEWS') IS NULL EXEC('CREATE SCHEMA FDE_VIEWS');
GO
CREATE OR ALTER VIEW FDE_VIEWS.VW_ACTIVE_FLEET AS
SELECT TS_UTC AS [Timestamp], V_LAT AS Latitude, V_LON AS Longitude,
       CAST(IOT_TEMP_VAL_C AS FLOAT) AS Current_Temperature_C,
       CGO_COND_CD AS Cargo_Condition_Code, RISK_CLS_TXT AS Risk_Classification,
       DELAY_PROB_DEC AS Delay_Probability, PRT_CNG_LVL AS Port_Congestion_Level,
       RT_RSK_IDX AS Route_Risk_Index
FROM dbo.TBL_SC_FLEET_HIST_RAW;
GO
IF SUSER_ID('USR_FDE_RO') IS NULL
    THROW 50001, 'Provision the restricted USR_FDE_RO login before running this section.', 1;
IF USER_ID('USR_FDE_RO') IS NULL CREATE USER USR_FDE_RO FOR LOGIN USR_FDE_RO;
GO
GRANT SELECT ON FDE_VIEWS.VW_ACTIVE_FLEET TO USR_FDE_RO;
DENY SELECT ON dbo.TBL_SC_FLEET_HIST_RAW TO USR_FDE_RO;
DENY INSERT, UPDATE, DELETE, ALTER ON SCHEMA::dbo TO USR_FDE_RO;
DENY INSERT, UPDATE, DELETE, ALTER ON SCHEMA::FDE_VIEWS TO USR_FDE_RO;
-- Do not add this account to db_owner, db_datareader or server administrator roles.
-- GO requires a SQL Server client (for example the VS Code MSSQL extension).
GO
