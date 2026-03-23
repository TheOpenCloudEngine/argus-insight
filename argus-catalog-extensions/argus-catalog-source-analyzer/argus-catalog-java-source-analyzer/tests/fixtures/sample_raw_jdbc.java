package com.example.legacy;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.Statement;

public class LegacyUserDao {

    private Connection connection;

    public List<User> findAll() throws Exception {
        Statement stmt = connection.createStatement();
        ResultSet rs = stmt.executeQuery("SELECT * FROM users WHERE active = 1");
        // process results
        return null;
    }

    public void insertUser(String name, String email) throws Exception {
        PreparedStatement ps = connection.prepareStatement("INSERT INTO users (username, email) VALUES (?, ?)");
        ps.setString(1, name);
        ps.setString(2, email);
        ps.executeUpdate();
    }

    public void updateStatus(Long id, boolean active) throws Exception {
        String sql = "UPDATE users SET active = ? WHERE id = ?";
        PreparedStatement ps = connection.prepareStatement(sql);
        ps.setBoolean(1, active);
        ps.setLong(2, id);
        ps.executeUpdate();
    }

    public void deleteOldOrders() throws Exception {
        Statement stmt = connection.createStatement();
        stmt.executeUpdate("DELETE FROM orders WHERE created_at < '2020-01-01'");
    }

    public List<Map<String, Object>> findOrdersWithItems(Long userId) throws Exception {
        String sql = "SELECT o.order_no, oi.product_name, oi.quantity FROM orders o JOIN order_items oi ON o.id = oi.order_id WHERE o.user_id = ?";
        PreparedStatement ps = connection.prepareStatement(sql);
        ps.setLong(1, userId);
        ResultSet rs = ps.executeQuery();
        return null;
    }
}
