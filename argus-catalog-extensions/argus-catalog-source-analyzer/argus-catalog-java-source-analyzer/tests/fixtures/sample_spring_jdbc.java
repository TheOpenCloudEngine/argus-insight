package com.example.repository;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;
import java.sql.ResultSet;
import java.sql.SQLException;

@Repository
public class UserJdbcRepository {

    private final JdbcTemplate jdbcTemplate;

    public UserJdbcRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public List<User> findAll() {
        return jdbcTemplate.query("SELECT id, username, email FROM users ORDER BY id", userRowMapper);
    }

    public User findById(Long id) {
        return jdbcTemplate.queryForObject("SELECT id, username, email FROM users WHERE id = ?", userRowMapper, id);
    }

    public List<Map<String, Object>> findUserOrders(Long userId) {
        return jdbcTemplate.queryForList("SELECT o.order_no, o.total FROM orders o WHERE o.user_id = ?", userId);
    }

    public int insert(User user) {
        return jdbcTemplate.update("INSERT INTO users (username, email) VALUES (?, ?)", user.getUsername(), user.getEmail());
    }

    public int updateEmail(Long id, String email) {
        return jdbcTemplate.update("UPDATE users SET email = ? WHERE id = ?", email, id);
    }

    public int deleteById(Long id) {
        return jdbcTemplate.update("DELETE FROM users WHERE id = ?", id);
    }

    public int[] batchInsertRoles(List<Object[]> batchArgs) {
        return jdbcTemplate.batchUpdate("INSERT INTO user_roles (user_id, role_id) VALUES (?, ?)", batchArgs);
    }

    public void createTable() {
        jdbcTemplate.execute("CREATE TABLE IF NOT EXISTS audit_log (id BIGINT PRIMARY KEY, action VARCHAR(255), created_at TIMESTAMP)");
    }
}
