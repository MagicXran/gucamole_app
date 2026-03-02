-- MySQL dump 10.13  Distrib 8.4.8, for Linux (x86_64)
--
-- Host: localhost    Database: guacamole_db
-- ------------------------------------------------------
-- Server version	8.4.8

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `guacamole_db`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `guacamole_db` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `guacamole_db`;

--
-- Table structure for table `guacamole_connection`
--

DROP TABLE IF EXISTS `guacamole_connection`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection` (
  `connection_id` int NOT NULL AUTO_INCREMENT,
  `connection_name` varchar(128) NOT NULL,
  `parent_id` int DEFAULT NULL,
  `protocol` varchar(32) NOT NULL,
  `proxy_port` int DEFAULT NULL,
  `proxy_hostname` varchar(512) DEFAULT NULL,
  `proxy_encryption_method` enum('NONE','SSL') DEFAULT NULL,
  `max_connections` int DEFAULT NULL,
  `max_connections_per_user` int DEFAULT NULL,
  `connection_weight` int DEFAULT NULL,
  `failover_only` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`connection_id`),
  UNIQUE KEY `connection_name_parent` (`connection_name`,`parent_id`),
  KEY `guacamole_connection_ibfk_1` (`parent_id`),
  CONSTRAINT `guacamole_connection_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `guacamole_connection_group` (`connection_group_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection`
--

LOCK TABLES `guacamole_connection` WRITE;
/*!40000 ALTER TABLE `guacamole_connection` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_connection_attribute`
--

DROP TABLE IF EXISTS `guacamole_connection_attribute`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection_attribute` (
  `connection_id` int NOT NULL,
  `attribute_name` varchar(128) NOT NULL,
  `attribute_value` varchar(4096) NOT NULL,
  PRIMARY KEY (`connection_id`,`attribute_name`),
  KEY `connection_id` (`connection_id`),
  CONSTRAINT `guacamole_connection_attribute_ibfk_1` FOREIGN KEY (`connection_id`) REFERENCES `guacamole_connection` (`connection_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection_attribute`
--

LOCK TABLES `guacamole_connection_attribute` WRITE;
/*!40000 ALTER TABLE `guacamole_connection_attribute` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection_attribute` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_connection_group`
--

DROP TABLE IF EXISTS `guacamole_connection_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection_group` (
  `connection_group_id` int NOT NULL AUTO_INCREMENT,
  `parent_id` int DEFAULT NULL,
  `connection_group_name` varchar(128) NOT NULL,
  `type` enum('ORGANIZATIONAL','BALANCING') NOT NULL DEFAULT 'ORGANIZATIONAL',
  `max_connections` int DEFAULT NULL,
  `max_connections_per_user` int DEFAULT NULL,
  `enable_session_affinity` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`connection_group_id`),
  UNIQUE KEY `connection_group_name_parent` (`connection_group_name`,`parent_id`),
  KEY `guacamole_connection_group_ibfk_1` (`parent_id`),
  CONSTRAINT `guacamole_connection_group_ibfk_1` FOREIGN KEY (`parent_id`) REFERENCES `guacamole_connection_group` (`connection_group_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection_group`
--

LOCK TABLES `guacamole_connection_group` WRITE;
/*!40000 ALTER TABLE `guacamole_connection_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_connection_group_attribute`
--

DROP TABLE IF EXISTS `guacamole_connection_group_attribute`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection_group_attribute` (
  `connection_group_id` int NOT NULL,
  `attribute_name` varchar(128) NOT NULL,
  `attribute_value` varchar(4096) NOT NULL,
  PRIMARY KEY (`connection_group_id`,`attribute_name`),
  KEY `connection_group_id` (`connection_group_id`),
  CONSTRAINT `guacamole_connection_group_attribute_ibfk_1` FOREIGN KEY (`connection_group_id`) REFERENCES `guacamole_connection_group` (`connection_group_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection_group_attribute`
--

LOCK TABLES `guacamole_connection_group_attribute` WRITE;
/*!40000 ALTER TABLE `guacamole_connection_group_attribute` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection_group_attribute` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_connection_group_permission`
--

DROP TABLE IF EXISTS `guacamole_connection_group_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection_group_permission` (
  `entity_id` int NOT NULL,
  `connection_group_id` int NOT NULL,
  `permission` enum('READ','UPDATE','DELETE','ADMINISTER') NOT NULL,
  PRIMARY KEY (`entity_id`,`connection_group_id`,`permission`),
  KEY `guacamole_connection_group_permission_ibfk_1` (`connection_group_id`),
  CONSTRAINT `guacamole_connection_group_permission_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE,
  CONSTRAINT `guacamole_connection_group_permission_ibfk_1` FOREIGN KEY (`connection_group_id`) REFERENCES `guacamole_connection_group` (`connection_group_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection_group_permission`
--

LOCK TABLES `guacamole_connection_group_permission` WRITE;
/*!40000 ALTER TABLE `guacamole_connection_group_permission` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection_group_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_connection_history`
--

DROP TABLE IF EXISTS `guacamole_connection_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection_history` (
  `history_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `username` varchar(128) NOT NULL,
  `remote_host` varchar(256) DEFAULT NULL,
  `connection_id` int DEFAULT NULL,
  `connection_name` varchar(128) NOT NULL,
  `sharing_profile_id` int DEFAULT NULL,
  `sharing_profile_name` varchar(128) DEFAULT NULL,
  `start_date` datetime NOT NULL,
  `end_date` datetime DEFAULT NULL,
  PRIMARY KEY (`history_id`),
  KEY `user_id` (`user_id`),
  KEY `connection_id` (`connection_id`),
  KEY `sharing_profile_id` (`sharing_profile_id`),
  KEY `start_date` (`start_date`),
  KEY `end_date` (`end_date`),
  KEY `connection_start_date` (`connection_id`,`start_date`),
  CONSTRAINT `guacamole_connection_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `guacamole_user` (`user_id`) ON DELETE SET NULL,
  CONSTRAINT `guacamole_connection_history_ibfk_2` FOREIGN KEY (`connection_id`) REFERENCES `guacamole_connection` (`connection_id`) ON DELETE SET NULL,
  CONSTRAINT `guacamole_connection_history_ibfk_3` FOREIGN KEY (`sharing_profile_id`) REFERENCES `guacamole_sharing_profile` (`sharing_profile_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=52 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection_history`
--

LOCK TABLES `guacamole_connection_history` WRITE;
/*!40000 ALTER TABLE `guacamole_connection_history` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_connection_parameter`
--

DROP TABLE IF EXISTS `guacamole_connection_parameter`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection_parameter` (
  `connection_id` int NOT NULL,
  `parameter_name` varchar(128) NOT NULL,
  `parameter_value` varchar(4096) NOT NULL,
  PRIMARY KEY (`connection_id`,`parameter_name`),
  CONSTRAINT `guacamole_connection_parameter_ibfk_1` FOREIGN KEY (`connection_id`) REFERENCES `guacamole_connection` (`connection_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection_parameter`
--

LOCK TABLES `guacamole_connection_parameter` WRITE;
/*!40000 ALTER TABLE `guacamole_connection_parameter` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection_parameter` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_connection_permission`
--

DROP TABLE IF EXISTS `guacamole_connection_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_connection_permission` (
  `entity_id` int NOT NULL,
  `connection_id` int NOT NULL,
  `permission` enum('READ','UPDATE','DELETE','ADMINISTER') NOT NULL,
  PRIMARY KEY (`entity_id`,`connection_id`,`permission`),
  KEY `guacamole_connection_permission_ibfk_1` (`connection_id`),
  CONSTRAINT `guacamole_connection_permission_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE,
  CONSTRAINT `guacamole_connection_permission_ibfk_1` FOREIGN KEY (`connection_id`) REFERENCES `guacamole_connection` (`connection_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_connection_permission`
--

LOCK TABLES `guacamole_connection_permission` WRITE;
/*!40000 ALTER TABLE `guacamole_connection_permission` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_connection_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_entity`
--

DROP TABLE IF EXISTS `guacamole_entity`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_entity` (
  `entity_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(128) NOT NULL,
  `type` enum('USER','USER_GROUP') NOT NULL,
  PRIMARY KEY (`entity_id`),
  UNIQUE KEY `guacamole_entity_name_scope` (`type`,`name`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_entity`
--

LOCK TABLES `guacamole_entity` WRITE;
/*!40000 ALTER TABLE `guacamole_entity` DISABLE KEYS */;
INSERT INTO `guacamole_entity` VALUES (1,'guacadmin','USER');
/*!40000 ALTER TABLE `guacamole_entity` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_sharing_profile`
--

DROP TABLE IF EXISTS `guacamole_sharing_profile`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_sharing_profile` (
  `sharing_profile_id` int NOT NULL AUTO_INCREMENT,
  `sharing_profile_name` varchar(128) NOT NULL,
  `primary_connection_id` int NOT NULL,
  PRIMARY KEY (`sharing_profile_id`),
  UNIQUE KEY `sharing_profile_name_primary` (`sharing_profile_name`,`primary_connection_id`),
  KEY `guacamole_sharing_profile_ibfk_1` (`primary_connection_id`),
  CONSTRAINT `guacamole_sharing_profile_ibfk_1` FOREIGN KEY (`primary_connection_id`) REFERENCES `guacamole_connection` (`connection_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_sharing_profile`
--

LOCK TABLES `guacamole_sharing_profile` WRITE;
/*!40000 ALTER TABLE `guacamole_sharing_profile` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_sharing_profile` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_sharing_profile_attribute`
--

DROP TABLE IF EXISTS `guacamole_sharing_profile_attribute`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_sharing_profile_attribute` (
  `sharing_profile_id` int NOT NULL,
  `attribute_name` varchar(128) NOT NULL,
  `attribute_value` varchar(4096) NOT NULL,
  PRIMARY KEY (`sharing_profile_id`,`attribute_name`),
  KEY `sharing_profile_id` (`sharing_profile_id`),
  CONSTRAINT `guacamole_sharing_profile_attribute_ibfk_1` FOREIGN KEY (`sharing_profile_id`) REFERENCES `guacamole_sharing_profile` (`sharing_profile_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_sharing_profile_attribute`
--

LOCK TABLES `guacamole_sharing_profile_attribute` WRITE;
/*!40000 ALTER TABLE `guacamole_sharing_profile_attribute` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_sharing_profile_attribute` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_sharing_profile_parameter`
--

DROP TABLE IF EXISTS `guacamole_sharing_profile_parameter`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_sharing_profile_parameter` (
  `sharing_profile_id` int NOT NULL,
  `parameter_name` varchar(128) NOT NULL,
  `parameter_value` varchar(4096) NOT NULL,
  PRIMARY KEY (`sharing_profile_id`,`parameter_name`),
  CONSTRAINT `guacamole_sharing_profile_parameter_ibfk_1` FOREIGN KEY (`sharing_profile_id`) REFERENCES `guacamole_sharing_profile` (`sharing_profile_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_sharing_profile_parameter`
--

LOCK TABLES `guacamole_sharing_profile_parameter` WRITE;
/*!40000 ALTER TABLE `guacamole_sharing_profile_parameter` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_sharing_profile_parameter` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_sharing_profile_permission`
--

DROP TABLE IF EXISTS `guacamole_sharing_profile_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_sharing_profile_permission` (
  `entity_id` int NOT NULL,
  `sharing_profile_id` int NOT NULL,
  `permission` enum('READ','UPDATE','DELETE','ADMINISTER') NOT NULL,
  PRIMARY KEY (`entity_id`,`sharing_profile_id`,`permission`),
  KEY `guacamole_sharing_profile_permission_ibfk_1` (`sharing_profile_id`),
  CONSTRAINT `guacamole_sharing_profile_permission_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE,
  CONSTRAINT `guacamole_sharing_profile_permission_ibfk_1` FOREIGN KEY (`sharing_profile_id`) REFERENCES `guacamole_sharing_profile` (`sharing_profile_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_sharing_profile_permission`
--

LOCK TABLES `guacamole_sharing_profile_permission` WRITE;
/*!40000 ALTER TABLE `guacamole_sharing_profile_permission` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_sharing_profile_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_system_permission`
--

DROP TABLE IF EXISTS `guacamole_system_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_system_permission` (
  `entity_id` int NOT NULL,
  `permission` enum('CREATE_CONNECTION','CREATE_CONNECTION_GROUP','CREATE_SHARING_PROFILE','CREATE_USER','CREATE_USER_GROUP','AUDIT','ADMINISTER') NOT NULL,
  PRIMARY KEY (`entity_id`,`permission`),
  CONSTRAINT `guacamole_system_permission_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_system_permission`
--

LOCK TABLES `guacamole_system_permission` WRITE;
/*!40000 ALTER TABLE `guacamole_system_permission` DISABLE KEYS */;
INSERT INTO `guacamole_system_permission` VALUES (1,'CREATE_CONNECTION'),(1,'CREATE_CONNECTION_GROUP'),(1,'CREATE_SHARING_PROFILE'),(1,'CREATE_USER'),(1,'CREATE_USER_GROUP'),(1,'ADMINISTER');
/*!40000 ALTER TABLE `guacamole_system_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user`
--

DROP TABLE IF EXISTS `guacamole_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `entity_id` int NOT NULL,
  `password_hash` binary(32) NOT NULL,
  `password_salt` binary(32) DEFAULT NULL,
  `password_date` datetime NOT NULL,
  `disabled` tinyint(1) NOT NULL DEFAULT '0',
  `expired` tinyint(1) NOT NULL DEFAULT '0',
  `access_window_start` time DEFAULT NULL,
  `access_window_end` time DEFAULT NULL,
  `valid_from` date DEFAULT NULL,
  `valid_until` date DEFAULT NULL,
  `timezone` varchar(64) DEFAULT NULL,
  `full_name` varchar(256) DEFAULT NULL,
  `email_address` varchar(256) DEFAULT NULL,
  `organization` varchar(256) DEFAULT NULL,
  `organizational_role` varchar(256) DEFAULT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `guacamole_user_single_entity` (`entity_id`),
  CONSTRAINT `guacamole_user_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user`
--

LOCK TABLES `guacamole_user` WRITE;
/*!40000 ALTER TABLE `guacamole_user` DISABLE KEYS */;
INSERT INTO `guacamole_user` VALUES (1,1,0xCA458A7D494E3BE824F5E1E175A1556C0F8EEF2C2D7DF3633BEC4A29C4411960,0xFE24ADC5E11E2B25288D1704ABE67A79E342ECC26064CE69C5B3177795A82264,'2026-03-01 22:32:17',0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL);
/*!40000 ALTER TABLE `guacamole_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_attribute`
--

DROP TABLE IF EXISTS `guacamole_user_attribute`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_attribute` (
  `user_id` int NOT NULL,
  `attribute_name` varchar(128) NOT NULL,
  `attribute_value` varchar(4096) NOT NULL,
  PRIMARY KEY (`user_id`,`attribute_name`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `guacamole_user_attribute_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `guacamole_user` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_attribute`
--

LOCK TABLES `guacamole_user_attribute` WRITE;
/*!40000 ALTER TABLE `guacamole_user_attribute` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_user_attribute` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_group`
--

DROP TABLE IF EXISTS `guacamole_user_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_group` (
  `user_group_id` int NOT NULL AUTO_INCREMENT,
  `entity_id` int NOT NULL,
  `disabled` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`user_group_id`),
  UNIQUE KEY `guacamole_user_group_single_entity` (`entity_id`),
  CONSTRAINT `guacamole_user_group_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_group`
--

LOCK TABLES `guacamole_user_group` WRITE;
/*!40000 ALTER TABLE `guacamole_user_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_user_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_group_attribute`
--

DROP TABLE IF EXISTS `guacamole_user_group_attribute`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_group_attribute` (
  `user_group_id` int NOT NULL,
  `attribute_name` varchar(128) NOT NULL,
  `attribute_value` varchar(4096) NOT NULL,
  PRIMARY KEY (`user_group_id`,`attribute_name`),
  KEY `user_group_id` (`user_group_id`),
  CONSTRAINT `guacamole_user_group_attribute_ibfk_1` FOREIGN KEY (`user_group_id`) REFERENCES `guacamole_user_group` (`user_group_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_group_attribute`
--

LOCK TABLES `guacamole_user_group_attribute` WRITE;
/*!40000 ALTER TABLE `guacamole_user_group_attribute` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_user_group_attribute` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_group_member`
--

DROP TABLE IF EXISTS `guacamole_user_group_member`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_group_member` (
  `user_group_id` int NOT NULL,
  `member_entity_id` int NOT NULL,
  PRIMARY KEY (`user_group_id`,`member_entity_id`),
  KEY `guacamole_user_group_member_entity_id` (`member_entity_id`),
  CONSTRAINT `guacamole_user_group_member_entity_id` FOREIGN KEY (`member_entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE,
  CONSTRAINT `guacamole_user_group_member_parent_id` FOREIGN KEY (`user_group_id`) REFERENCES `guacamole_user_group` (`user_group_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_group_member`
--

LOCK TABLES `guacamole_user_group_member` WRITE;
/*!40000 ALTER TABLE `guacamole_user_group_member` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_user_group_member` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_group_permission`
--

DROP TABLE IF EXISTS `guacamole_user_group_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_group_permission` (
  `entity_id` int NOT NULL,
  `affected_user_group_id` int NOT NULL,
  `permission` enum('READ','UPDATE','DELETE','ADMINISTER') NOT NULL,
  PRIMARY KEY (`entity_id`,`affected_user_group_id`,`permission`),
  KEY `guacamole_user_group_permission_affected_user_group` (`affected_user_group_id`),
  CONSTRAINT `guacamole_user_group_permission_affected_user_group` FOREIGN KEY (`affected_user_group_id`) REFERENCES `guacamole_user_group` (`user_group_id`) ON DELETE CASCADE,
  CONSTRAINT `guacamole_user_group_permission_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_group_permission`
--

LOCK TABLES `guacamole_user_group_permission` WRITE;
/*!40000 ALTER TABLE `guacamole_user_group_permission` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_user_group_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_history`
--

DROP TABLE IF EXISTS `guacamole_user_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_history` (
  `history_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `username` varchar(128) NOT NULL,
  `remote_host` varchar(256) DEFAULT NULL,
  `start_date` datetime NOT NULL,
  `end_date` datetime DEFAULT NULL,
  PRIMARY KEY (`history_id`),
  KEY `user_id` (`user_id`),
  KEY `start_date` (`start_date`),
  KEY `end_date` (`end_date`),
  KEY `user_start_date` (`user_id`,`start_date`),
  CONSTRAINT `guacamole_user_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `guacamole_user` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=92 DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_history`
--

LOCK TABLES `guacamole_user_history` WRITE;
/*!40000 ALTER TABLE `guacamole_user_history` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_user_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_password_history`
--

DROP TABLE IF EXISTS `guacamole_user_password_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_password_history` (
  `password_history_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `password_hash` binary(32) NOT NULL,
  `password_salt` binary(32) DEFAULT NULL,
  `password_date` datetime NOT NULL,
  PRIMARY KEY (`password_history_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `guacamole_user_password_history_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `guacamole_user` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_password_history`
--

LOCK TABLES `guacamole_user_password_history` WRITE;
/*!40000 ALTER TABLE `guacamole_user_password_history` DISABLE KEYS */;
/*!40000 ALTER TABLE `guacamole_user_password_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `guacamole_user_permission`
--

DROP TABLE IF EXISTS `guacamole_user_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `guacamole_user_permission` (
  `entity_id` int NOT NULL,
  `affected_user_id` int NOT NULL,
  `permission` enum('READ','UPDATE','DELETE','ADMINISTER') NOT NULL,
  PRIMARY KEY (`entity_id`,`affected_user_id`,`permission`),
  KEY `guacamole_user_permission_ibfk_1` (`affected_user_id`),
  CONSTRAINT `guacamole_user_permission_entity` FOREIGN KEY (`entity_id`) REFERENCES `guacamole_entity` (`entity_id`) ON DELETE CASCADE,
  CONSTRAINT `guacamole_user_permission_ibfk_1` FOREIGN KEY (`affected_user_id`) REFERENCES `guacamole_user` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `guacamole_user_permission`
--

LOCK TABLES `guacamole_user_permission` WRITE;
/*!40000 ALTER TABLE `guacamole_user_permission` DISABLE KEYS */;
INSERT INTO `guacamole_user_permission` VALUES (1,1,'READ'),(1,1,'UPDATE'),(1,1,'ADMINISTER');
/*!40000 ALTER TABLE `guacamole_user_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Current Database: `guacamole_portal_db`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `guacamole_portal_db` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `guacamole_portal_db`;

--
-- Table structure for table `portal_user`
--

DROP TABLE IF EXISTS `portal_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `username` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '登录用户名',
  `password_hash` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'bcrypt 哈希',
  `display_name` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '' COMMENT '显示名称',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portal_user`
--

LOCK TABLES `portal_user` WRITE;
/*!40000 ALTER TABLE `portal_user` DISABLE KEYS */;
INSERT INTO `portal_user` VALUES (1,'admin','$2b$12$.zHt5ZnYYg9BLJ8sXI84U.Doz2rhgbAbghicuxjUNz5vN3lFdlytu','管理员',1,'2026-03-02 15:53:32','2026-03-02 15:53:32'),(2,'test','$2b$12$L91JPIXfv6upob1STuLlJuIZqese8iUsJdf9G/YwYCw3mIzm7TJs6','测试用户',1,'2026-03-02 15:53:33','2026-03-02 15:53:33');
/*!40000 ALTER TABLE `portal_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `remote_app`
--

DROP TABLE IF EXISTS `remote_app`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `remote_app` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '显示名称',
  `icon` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT 'desktop' COMMENT '图标标识',
  `protocol` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'rdp',
  `hostname` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `port` int NOT NULL DEFAULT '3389',
  `rdp_username` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'RDP 登录用户名',
  `rdp_password` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'RDP 登录密码',
  `domain` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `security` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'nla' COMMENT 'nla/tls/rdp/any',
  `ignore_cert` tinyint(1) DEFAULT '1',
  `remote_app` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'RemoteApp，如 ||notepad',
  `remote_app_dir` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'RemoteApp 工作目录',
  `remote_app_args` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'RemoteApp 命令行参数',
  `is_active` tinyint(1) DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_active` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `remote_app`
--

LOCK TABLES `remote_app` WRITE;
/*!40000 ALTER TABLE `remote_app` DISABLE KEYS */;
INSERT INTO `remote_app` VALUES (1,'记事本','edit','rdp','192.168.1.8',3389,'xran','Nercar501','','nla',1,'||记事本',NULL,'记事本',1,'2026-03-01 22:37:57','2026-03-01 22:40:06'),(2,'计算器','calculate','rdp','192.168.1.8',3389,'xran','Nercar501','','nla',1,'||Windows Calculator',NULL,NULL,1,'2026-03-01 22:37:57','2026-03-01 22:40:06'),(3,'远程桌面','desktop','rdp','192.168.1.8',3389,'xran','Nercar501','','nla',1,NULL,NULL,NULL,1,'2026-03-01 22:37:57','2026-03-01 22:40:07');
/*!40000 ALTER TABLE `remote_app` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `remote_app_acl`
--

DROP TABLE IF EXISTS `remote_app_acl`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `remote_app_acl` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL COMMENT '用户ID（PoC阶段固定为1）',
  `app_id` bigint NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_user_app` (`user_id`,`app_id`),
  KEY `app_id` (`app_id`),
  CONSTRAINT `remote_app_acl_ibfk_1` FOREIGN KEY (`app_id`) REFERENCES `remote_app` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `remote_app_acl`
--

LOCK TABLES `remote_app_acl` WRITE;
/*!40000 ALTER TABLE `remote_app_acl` DISABLE KEYS */;
INSERT INTO `remote_app_acl` VALUES (1,1,1,'2026-03-01 22:37:57'),(2,1,2,'2026-03-01 22:37:57'),(3,1,3,'2026-03-01 22:37:57'),(5,2,1,'2026-03-02 15:53:53');
/*!40000 ALTER TABLE `remote_app_acl` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `token_cache`
--

DROP TABLE IF EXISTS `token_cache`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `token_cache` (
  `username` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Guacamole 用户名 (如 portal_u1)',
  `auth_token` varchar(256) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'Guacamole authToken',
  `data_source` varchar(64) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'json' COMMENT '数据源标识',
  `created_at` double NOT NULL COMMENT 'Unix timestamp (秒)',
  PRIMARY KEY (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `token_cache`
--

LOCK TABLES `token_cache` WRITE;
/*!40000 ALTER TABLE `token_cache` DISABLE KEYS */;
/*!40000 ALTER TABLE `token_cache` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-03-02 17:14:57
